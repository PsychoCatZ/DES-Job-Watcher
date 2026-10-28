"""Проверить замороженный пакет medium/high; --live явно включает платные запросы."""

import argparse
import json
import os
from pathlib import Path

import httpx

from des_job_watcher.effort_comparison import load_jobs, run_comparison, write_comparison_report
from des_job_watcher.history import History
from des_job_watcher.openai_adapter import analyze_once
from des_job_watcher.secret_input import read_secret

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pack', type=Path, required=True)
    parser.add_argument('--live', action='store_true')
    args = parser.parse_args()
    try:
        jobs = load_jobs(args.pack)
        pending = []
        for job in jobs:
            path = args.pack / f"{job['id']}.result.json"
            if path.exists():
                record = json.loads(path.read_text(encoding='utf-8'))
                if record.get('status') != 'completed' or record.get('request', {}).get('api_body_sha256') != job['request']['api_body_sha256']:
                    raise ValueError('Сохранённый ответ неуспешен или отличается от плана. Повтор отключён.')
            else:
                pending.append(job)
            print(f"{job['id']} | {job['case_id']} | {'новый запрос' if job in pending else 'ответ сохранён'}")
        write_comparison_report(args.pack, jobs)
        print(f'Предстоит платных запросов: {len(pending)}. Модель: gpt-6-luna. Лимит: 8192. Повторов нет.')
        if not args.live or not pending:
            print('Сеть и ключ не использовались.')
            return 0
        with History(ROOT / 'data/watcher.sqlite3') as history:
            for job in pending:
                if history.attempt_status('effort_comparison:' + job['request']['api_body_sha256']):
                    raise ValueError('Одна из попыток уже зарегистрирована. Автоматического повтора нет.')
            key = os.environ.get('OPENAI_API_KEY') or read_secret('OpenAI API key (*): ').strip()
            with httpx.Client(timeout=httpx.Timeout(240, connect=15), follow_redirects=False) as client:
                success = run_comparison(args.pack, jobs, history,
                    lambda payload, effort: analyze_once(payload, key, client, effort=effort))
        print(f'Отчёт: {args.pack / "report.md"}')
        return 0 if success else 1
    except (OSError, ValueError, KeyError) as error:
        print(f'Сравнение остановлено: {error}')
        return 1
    except KeyboardInterrupt:
        print('\nПрервано. Попытка остаётся зарегистрированной; не повторяйте запрос вслепую.')
        return 130


if __name__ == '__main__':
    raise SystemExit(main())
