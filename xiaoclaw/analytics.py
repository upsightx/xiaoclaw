"""xiaoclaw Analytics — Token usage tracking and statistics"""
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from collections import defaultdict
import threading

logger = logging.getLogger("xiaoclaw.Analytics")

STATS_DIR = Path.home() / ".xiaoclaw" / "stats"


@dataclass
class CallRecord:
    """Single API call record."""
    timestamp: float
    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    duration_ms: float
    success: bool
    error: Optional[str] = None


@dataclass 
class DailyStats:
    """Aggregated daily statistics."""
    date: str  # YYYY-MM-DD
    total_calls: int
    success_calls: int
    failed_calls: int
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    avg_duration_ms: float
    models: Dict[str, Dict[str, int]]  # {model_name: {calls, tokens}}
    providers: Dict[str, Dict[str, int]]  # {provider_name: {calls, tokens}}
    errors: List[Dict[str, Any]]  # List of {time, model, error}


class Analytics:
    """Token usage analytics with persistence."""
    
    def __init__(self, stats_dir: Optional[Path] = None):
        self.stats_dir = stats_dir or STATS_DIR
        self.stats_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._current_records: List[CallRecord] = []
        self._current_date = datetime.now().strftime("%Y-%m-%d")
        
    def _get_daily_file(self, date: str) -> Path:
        """Get stats file path for a date."""
        return self.stats_dir / f"stats_{date}.json"
    
    def record(self, model: str, provider: str, input_tokens: int, output_tokens: int,
               duration_ms: float, success: bool, error: Optional[str] = None) -> None:
        """Record an API call."""
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        
        with self._lock:
            # 如果日期变了，先保存之前的数据
            if today != self._current_date and self._current_records:
                self._save_daily_records(self._current_date, self._current_records)
                self._current_records = []
                self._current_date = today
            
            record = CallRecord(
                timestamp=now.timestamp(),
                model=model,
                provider=provider,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
                duration_ms=duration_ms,
                success=success,
                error=error
            )
            
            self._current_records.append(record)
            
            # 每 10 条自动保存一次
            if len(self._current_records) >= 10:
                self._save_daily_records(today, self._current_records)
                self._current_records = []
    
    def flush(self) -> None:
        """Explicitly flush current records to disk."""
        with self._lock:
            if self._current_records:
                self._save_daily_records(self._current_date, self._current_records)
                self._current_records = []
    
    def _save_daily_records(self, date: str, records: List[CallRecord]) -> None:
        """Save records to daily file."""
        if not records:
            return
            
        file_path = self._get_daily_file(date)
        
        # 读取现有数据 - catch specific exceptions
        existing = []
        if file_path.exists():
            try:
                with open(file_path, 'r') as f:
                    existing = json.load(f).get('records', [])
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Could not read existing stats file for {date}: {e}. Starting fresh.")
                existing = []
        
        # 合并
        all_records = existing + [asdict(r) for r in records]
        
        # 计算聚合统计
        daily = self._aggregate_records(all_records, date)
        
        with open(file_path, 'w') as f:
            json.dump({
                'date': date,
                'records': all_records,
                'summary': asdict(daily)
            }, f)
    
    def _aggregate_records(self, records: List[Dict], date: str) -> DailyStats:
        """Aggregate records into daily stats."""
        total_calls = len(records)
        success_calls = sum(1 for r in records if r['success'])
        failed_calls = total_calls - success_calls
        total_input = sum(r['input_tokens'] for r in records)
        total_output = sum(r['output_tokens'] for r in records)
        durations = [r['duration_ms'] for r in records if r['duration_ms'] > 0]
        avg_duration = sum(durations) / len(durations) if durations else 0
        
        # 按模型统计
        models = defaultdict(lambda: {'calls': 0, 'tokens': 0, 'input': 0, 'output': 0})
        for r in records:
            models[r['model']]['calls'] += 1
            models[r['model']]['tokens'] += r['total_tokens']
            models[r['model']]['input'] += r['input_tokens']
            models[r['model']]['output'] += r['output_tokens']
        
        # 按提供商统计
        providers = defaultdict(lambda: {'calls': 0, 'tokens': 0})
        for r in records:
            providers[r['provider']]['calls'] += 1
            providers[r['provider']]['tokens'] += r['total_tokens']
        
        # 错误记录（只保留最近 20 条）
        errors = [
            {'time': r['timestamp'], 'model': r['model'], 'error': r['error']}
            for r in records if not r['success'] and r['error']
        ][-20:]
        
        return DailyStats(
            date=date,
            total_calls=total_calls,
            success_calls=success_calls,
            failed_calls=failed_calls,
            total_input_tokens=total_input,
            total_output_tokens=total_output,
            total_tokens=total_input + total_output,
            avg_duration_ms=round(avg_duration, 2),
            models=dict(models),
            providers=dict(providers),
            errors=errors
        )
    
    def get_daily_stats(self, date: Optional[str] = None) -> Optional[DailyStats]:
        """Get stats for a specific date (read-only, no side effects)."""
        date = date or datetime.now().strftime("%Y-%m-%d")
        file_path = self._get_daily_file(date)
        
        # Don't flush records as a side effect - just read from file
        if not file_path.exists():
            return None
        
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
                summary = data.get('summary', {})
                return DailyStats(**summary)
        except (json.JSONDecodeError, KeyError, OSError) as e:
            logger.warning(f"Could not read stats file for {date}: {e}")
            return None
    
    def get_range_stats(self, start_date: str, end_date: str) -> Dict[str, Any]:
        """Get aggregated stats for a date range."""
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        
        total_calls = 0
        total_success = 0
        total_failed = 0
        total_tokens = 0
        total_input = 0
        total_output = 0
        total_duration = 0
        duration_count = 0
        all_models = defaultdict(lambda: {'calls': 0, 'tokens': 0, 'input': 0, 'output': 0})
        all_providers = defaultdict(lambda: {'calls': 0, 'tokens': 0})
        daily_data = []
        
        current = start
        while current <= end:
            date_str = current.strftime("%Y-%m-%d")
            daily = self.get_daily_stats(date_str)
            if daily:
                total_calls += daily.total_calls
                total_success += daily.success_calls
                total_failed += daily.failed_calls
                total_tokens += daily.total_tokens
                total_input += daily.total_input_tokens
                total_output += daily.total_output_tokens
                if daily.avg_duration_ms > 0:
                    total_duration += daily.avg_duration_ms * daily.total_calls
                    duration_count += daily.total_calls
                
                for model, data in daily.models.items():
                    all_models[model]['calls'] += data['calls']
                    all_models[model]['tokens'] += data['tokens']
                    all_models[model]['input'] += data.get('input', 0)
                    all_models[model]['output'] += data.get('output', 0)
                
                for provider, data in daily.providers.items():
                    all_providers[provider]['calls'] += data['calls']
                    all_providers[provider]['tokens'] += data['tokens']
                
                daily_data.append({
                    'date': date_str,
                    'calls': daily.total_calls,
                    'tokens': daily.total_tokens,
                    'success_rate': round(daily.success_calls / daily.total_calls * 100, 1) if daily.total_calls > 0 else 0
                })
            
            current += timedelta(days=1)
        
        success_rate = round(total_success / total_calls * 100, 1) if total_calls > 0 else 0
        avg_duration = round(total_duration / duration_count, 2) if duration_count > 0 else 0
        
        return {
            'period': {'start': start_date, 'end': end_date, 'days': (end - start).days + 1},
            'totals': {
                'calls': total_calls,
                'success': total_success,
                'failed': total_failed,
                'tokens': total_tokens,
                'input_tokens': total_input,
                'output_tokens': total_output,
                'avg_duration_ms': avg_duration
            },
            'success_rate': success_rate,
            'by_model': dict(all_models),
            'by_provider': dict(all_providers),
            'daily': daily_data
        }
    
    def get_recent_stats(self, days: int = 7) -> Dict[str, Any]:
        """Get stats for recent N days."""
        end = datetime.now()
        start = end - timedelta(days=days - 1)
        return self.get_range_stats(
            start.strftime("%Y-%m-%d"),
            end.strftime("%Y-%m-%d")
        )
    
    def print_report(self, days: int = 7) -> str:
        """Print a formatted report (respects XIAOCLAW_LANG)."""
        from .i18n import t, LANG
        stats = self.get_recent_stats(days)
        
        lines = []
        title = t("analytics_title", lang=LANG)
        lines.append(f"\n📊 {title} ({days} days)")
        lines.append("=" * 50)
        
        totals = stats['totals']
        lines.append(f"\n📈 {'Overall:' if LANG != 'zh' else '总体:'}")
        lines.append(f"  {t('analytics_requests', lang=LANG)}: {totals['calls']:,}")
        lines.append(f"  {t('analytics_success', lang=LANG)}:   {stats['success_rate']}%")
        lines.append(f"  {t('analytics_tokens', lang=LANG)}: {totals['tokens']:,}")
        lines.append(f"  Input:     {totals['input_tokens']:,}")
        lines.append(f"  Output:    {totals['output_tokens']:,}")
        lines.append(f"  Avg time:  {totals['avg_duration_ms']:.0f}ms")
        
        if stats['by_model']:
            lines.append(f"\n🤖 {'By Model:' if LANG != 'zh' else '按模型:'}")
            for model, data in sorted(stats['by_model'].items(), key=lambda x: -x[1]['tokens']):
                lines.append(f"  {model}:")
                lines.append(f"    Calls: {data['calls']:,} | Tokens: {data['tokens']:,}")
                lines.append(f"    Input: {data['input']:,} | Output: {data['output']:,}")
        
        if stats['by_provider']:
            lines.append(f"\n🔌 {'By Provider:' if LANG != 'zh' else '按提供商:'}")
            for provider, data in sorted(stats['by_provider'].items(), key=lambda x: -x[1]['tokens']):
                lines.append(f"  {provider}: {data['calls']:,} calls, {data['tokens']:,} tokens")
        
        if stats['daily']:
            lines.append(f"\n📅 {'Daily:' if LANG != 'zh' else '每日统计:'}")
            for d in stats['daily'][-7:]:  # 最近 7 天
                bar = "█" * min(20, d['tokens'] // 1000)
                lines.append(f"  {d['date']}: {d['calls']:>3} calls | {d['tokens']:>7,} tokens | {d['success_rate']:.0f}% {bar}")
        
        return "\n".join(lines)
