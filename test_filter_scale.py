"""Quick test to estimate daily job volume and costs.

Tests a sample of companies to extrapolate total volume.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx

from src.config import settings
from src.detection.greenhouse import GreenhouseScraper
from src.filter.matcher import JobMatcher


async def main() -> None:
    print("\n" + "=" * 80)
    print("FILTER EFFECTIVENESS TEST — Estimating Daily Job Volume & Costs")
    print("=" * 80 + "\n")

    matcher = JobMatcher(settings)

    # Load company list
    cache_dir = Path("data/cache")
    if not cache_dir.exists():
        print("❌ Company cache not found. Run startup first to sync companies.")
        return

    # Load Greenhouse companies (largest source)
    gh_tokens = json.load(open(cache_dir / "greenhouse_companies.json"))
    print(f"Greenhouse has {len(gh_tokens):,} companies registered")

    # Sample first 20 companies to get real data
    sample_size = 20
    total_jobs_sampled = 0
    matched_jobs_sampled = 0

    print(f"\nSampling {sample_size} companies...\n")

    async with httpx.AsyncClient(timeout=60.0) as client:
        for i, token in enumerate(gh_tokens[:sample_size]):
            try:
                scraper = GreenhouseScraper(board_token=token, company_name=token)
                jobs = await scraper.fetch_jobs(client)

                matched = sum(
                    1
                    for job in jobs
                    if matcher.match(job.title, job.location, job.description_text or "").matched
                )

                total_jobs_sampled += len(jobs)
                matched_jobs_sampled += matched

                if len(jobs) > 0:
                    match_pct = (matched / len(jobs)) * 100
                    print(f"  {i+1:2d}. {token:30s} → {len(jobs):3d} jobs, {matched:2d} matched ({match_pct:5.1f}%)")
            except Exception as e:
                print(f"  {i+1:2d}. {token:30s} → Error: {str(e)[:40]}")

    if total_jobs_sampled == 0:
        print("\n❌ No jobs found. API may be timing out or companies are empty.")
        return

    # Calculate averages
    avg_jobs_per_company = total_jobs_sampled / sample_size
    match_rate = matched_jobs_sampled / total_jobs_sampled

    print(f"\n" + "=" * 80)
    print("EXTRAPOLATED ESTIMATES (based on {sample_size} company sample)")
    print("=" * 80)

    # Greenhouse (4,516 companies)
    gh_jobs_per_day = int(4516 * avg_jobs_per_company)
    gh_matched_per_day = int(gh_jobs_per_day * match_rate)

    print(f"\n📊 GREENHOUSE (4,516 companies)")
    print(f"   Average jobs/company: {avg_jobs_per_company:.1f}")
    print(f"   Match rate: {match_rate*100:.1f}%")
    print(f"   Estimated jobs/day: {gh_jobs_per_day:,}")
    print(f"   Estimated matched/day: {gh_matched_per_day:,}")

    # Lever (similar but smaller: 947 companies, ~50% of Greenhouse volume per company)
    lv_jobs_per_day = int(947 * (avg_jobs_per_company * 0.5))
    lv_matched_per_day = int(lv_jobs_per_day * match_rate)
    print(f"\n📊 LEVER (947 companies, ~50% volume)")
    print(f"   Estimated jobs/day: {lv_jobs_per_day:,}")
    print(f"   Estimated matched/day: {lv_matched_per_day:,}")

    # Ashby (smaller: 799 companies, ~30% of Greenhouse)
    ab_jobs_per_day = int(799 * (avg_jobs_per_company * 0.3))
    ab_matched_per_day = int(ab_jobs_per_day * match_rate)
    print(f"\n📊 ASHBY (799 companies, ~30% volume)")
    print(f"   Estimated jobs/day: {ab_jobs_per_day:,}")
    print(f"   Estimated matched/day: {ab_matched_per_day:,}")

    # HN (monthly thread, ~200 jobs)
    hn_matched_per_day = int(200 * match_rate / 30)
    print(f"\n📊 HN WHO IS HIRING (monthly, ~200 jobs)")
    print(f"   Estimated matched/day: {hn_matched_per_day:,}")

    # Total
    total_daily_jobs = gh_jobs_per_day + lv_jobs_per_day + ab_jobs_per_day
    total_matched_per_day = gh_matched_per_day + lv_matched_per_day + ab_matched_per_day + hn_matched_per_day

    print(f"\n" + "=" * 80)
    print("TOTAL DAILY ESTIMATES")
    print("=" * 80)
    print(f"\nTotal jobs scraped/day: {total_daily_jobs:,}")
    print(f"Total jobs passing filter: {total_matched_per_day:,} Discord messages/day")
    print(f"Filter effectiveness: {(total_matched_per_day/total_daily_jobs)*100:.1f}%")

    # Cost analysis
    print(f"\n" + "=" * 80)
    print("💰 COST ANALYSIS")
    print("=" * 80)

    # Detection cost (just API calls, minimal)
    detection_cost_per_day = 0  # APIs are free
    print(f"\nDetection (job scraping): $0/day (APIs are free)")

    # Discord notification cost (only for matched jobs)
    discord_messages = total_matched_per_day
    discord_cost_per_day = discord_messages * 0.00001  # Very cheap, just webhook calls
    print(f"\nDiscord notifications: {discord_messages:,} messages/day")
    print(f"  Cost/day: ${discord_cost_per_day:.2f}")

    # Resume generation (only for matched jobs, using Haiku)
    # Selector: ~800 tokens = $0.003
    # ATS pass: ~3000 tokens = $0.011
    # Total: ~$0.014 per resume
    resume_cost = 0.014
    resume_cost_per_day = discord_messages * resume_cost
    resume_cost_per_month = resume_cost_per_day * 30

    print(f"\nResume generation (for matched jobs only):")
    print(f"  {discord_messages:,} resumes/day × ${resume_cost}/resume")
    print(f"  Cost/day: ${resume_cost_per_day:.2f}")
    print(f"  Cost/month: ${resume_cost_per_month:.2f}")

    # Total
    total_cost_per_day = discord_cost_per_day + resume_cost_per_day
    total_cost_per_month = total_cost_per_day * 30

    print(f"\n💵 TOTAL COST/DAY: ${total_cost_per_day:.2f}")
    print(f"💵 TOTAL COST/MONTH: ${total_cost_per_month:.2f}")

    # Recommendations
    print(f"\n" + "=" * 80)
    print("⚠️  RECOMMENDATIONS")
    print("=" * 80)

    if total_matched_per_day > 30:
        print(f"\n🔴 HIGH VOLUME: {total_matched_per_day:,} Discord messages/day")
        print(f"   This is A LOT of work to review manually.\n")
        print(f"   RECOMMENDATION: Add HUMAN-IN-THE-LOOP approval")
        print(f"   - User reviews matched jobs before resume generation")
        print(f"   - Resume generation only for APPROVED jobs")
        print(f"   - Reduces Discord spam and token costs\n")

        # Calculate savings with approval
        approval_rate = 0.3  # Assume user approves 30%
        approved_per_day = int(total_matched_per_day * approval_rate)
        savings = (total_matched_per_day - approved_per_day) * resume_cost
        savings_per_month = savings * 30

        print(f"   IF you approve 30% of jobs:")
        print(f"   - Resume generation: {approved_per_day} resumes/day")
        print(f"   - Cost/day: ${approved_per_day * resume_cost:.2f}")
        print(f"   - Savings/month: ${savings_per_month:.2f}")
        print(f"   - Time to review: ~{total_matched_per_day * 2 / 60:.0f} mins/day")

    elif total_matched_per_day > 10:
        print(f"\n🟡 MEDIUM VOLUME: {total_matched_per_day:,} Discord messages/day")
        print(f"   Manageable but might be a lot to keep up with.\n")
        print(f"   OPTIONS:")
        print(f"   1. Fully automated (current setup)")
        print(f"      - Cost/month: ${total_cost_per_month:.2f}")
        print(f"      - Discord messages: {total_matched_per_day:,}/day")
        print(f"      - Your effort: Apply to jobs manually\n")
        print(f"   2. Add human approval (if too many)")
        print(f"      - Review filter results, approve/reject jobs")
        print(f"      - Resume generation only for approved jobs")
        print(f"      - Recommended if you can't keep up")

    else:
        print(f"\n🟢 LOW VOLUME: {total_matched_per_day:,} Discord messages/day")
        print(f"   Status: Fully automated is ideal")
        print(f"   - Cost/month: ${total_cost_per_month:.2f}")
        print(f"   - Very manageable, you'll receive very few messages")

    print(f"\n" + "=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
