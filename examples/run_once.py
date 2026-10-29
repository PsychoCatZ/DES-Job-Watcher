"""Один ограниченный проход поиска HH и анализа; без расписания и Telegram."""

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PROFILES = ('support', 'ai_data')


def run_step(name, arguments):
    print(f'\n=== {name} ===', flush=True)
    result = subprocess.run([sys.executable, '-m', *arguments], cwd=ROOT, check=False)
    if result.returncode:
        print(f'Этап остановлен: {name}; код {result.returncode}. Сохранённые результаты остаются на месте.', flush=True)
        return False
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', help='Сеть HH и платные запросы Luna')
    parser.add_argument('--details-per-profile', type=int, default=10)
    parser.add_argument('--analyses-per-profile', type=int, default=3)
    args = parser.parse_args()
    if not 1 <= args.details_per_profile <= 100 or not 1 <= args.analyses_per_profile <= 15:
        parser.error('Допустимые лимиты: 1–100 карточек и 1–15 анализов на профиль.')
    print('Профили: поддержка и AI-data. Один проход, без фонового режима и Telegram.', flush=True)
    print(f'Максимум: {2 * args.details_per_profile} новых карточек и {2 * args.analyses_per_profile} платных анализов.', flush=True)
    if not args.live:
        print('ПЛАН: сеть, ключи и база не использовались. Для выполнения добавь --live.', flush=True)
        return 0
    missing = [name for name in ('HH_USER_AGENT', 'HH_ACCESS_TOKEN', 'OPENAI_API_KEY') if not os.environ.get(name, '').strip()]
    if missing:
        print('Сначала настрой текущую сессию PowerShell через .\\scripts\\start_session.ps1. Не заданы: ' + ', '.join(missing), flush=True)
        return 1
    run_dir = ROOT / 'data' / 'hh_api' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    if not run_step('Поиск HH', ['examples.collect_hh', '--live', '--run-directory', str(run_dir)]):
        return 1
    candidates = str(run_dir / 'candidates.json')
    for profile in PROFILES:
        if not run_step(f'Полные карточки: {profile}', ['examples.fetch_hh_details', '--input', candidates,
                        '--profile', profile, '--limit', str(args.details_per_profile), '--live']):
            return 1
    for profile in PROFILES:
        if not run_step(f'Анализ Luna: {profile}', ['examples.analyze_saved', '--input', candidates,
                        '--profile', profile, '--limit', str(args.analyses_per_profile), '--live']):
            return 1
    print(f'\nПроход завершён. Поиск: {run_dir}. Отчёты анализов напечатаны на этапах Luna.', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
