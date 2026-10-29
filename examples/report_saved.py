"""Отчёт и сохранение отдельных пересчётов политики. Без сети и LLM."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from des_job_watcher.history import History
from des_job_watcher.operational_policy import apply_policy, load_policy

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render_card(payload, review):
    current = review['assessment']
    analysis = current['analysis']
    vacancy = payload['vacancy']
    lines = [f"## {vacancy['name']}", '',
             f"Профиль: {payload['profile']['profile_id']} · HH ID: {vacancy['id']}", '',
             f"Ссылка: https://hh.ru/vacancy/{vacancy['id']}", '',
             f"Решение после локальной политики: **{current['decision']} / {current['delivery']['action']}**", '',
             f"Основная работа: {analysis['main_work']['summary']}", '',
             analysis['main_work']['reason'], '']
    if 'entry_readiness' in current:
        lines += [f"Готовность к основной работе сейчас: **{current['entry_readiness']}**. {current['readiness_reason']}", '']
        if current.get('readiness_routing', {}).get('advanced_core_gaps'):
            lines += ['Маршрут изменён из-за неподтверждённого ключевого требования высокого уровня. Это основание профессионального разбора, а не доказательство неспособности кандидата.', '']
    for correction in current.get('semantic_corrections', []):
        explanation = ('по известному отсутствию слуха' if correction['rule'] == 'known_hearing_unavailable'
                       else 'явный текст подтверждает удалёнку; избыточная ссылка на смешанное поле удалена')
        lines += [f"Проверка согласованности: {correction['path']} — {correction['before']} → {correction['after']}: {explanation}.", '']
    if review['overrides']:
        lines += ['**Основания изменения решения:**', '']
        for override in review['overrides']:
            lines += [override.get('reason', 'Требование оборудования для голосовой/видеосвязи.'), '']
            lines.extend('> ' + quote for quote in override['quotes'])
        lines.append('')
    condition = analysis['conditions']['communication']
    lines += [f"Коммуникация в исходном ответе: {condition['status']}. {condition['reason']}", '']
    requirements = [item for item in analysis['requirements'] if item['status'] != 'confirmed']
    if requirements:
        lines += ['Требования из исходного анализа, которые модель не подтвердила или сочла конфликтом:', '']
        lines.extend(f"- {item['text']} — {item['status']}: {item['reason']}" for item in requirements)
        lines.append('')
    if review.get('kind') == 'new_analysis_with_operational_policy':
        lines += ['Новый ответ Luna с отдельной программной проверкой и применением текущей политики.', '']
    else:
        lines += ['Это пересчёт сохранённого анализа, не новый ответ Luna. Новые сведения о компьютере и переносе опыта не переоценивают старые требования автоматически.', '']
    return lines


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch', type=Path, action='append', required=True)
    args = parser.parse_args()
    cards = []
    seen = set()
    output = ROOT / 'data' / 'reports' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    output.mkdir(parents=True, exist_ok=False)
    policy = load_policy()
    policy_hash = hashlib.sha256(json.dumps(policy, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    with History(ROOT / 'data/watcher.sqlite3') as history:
        for batch in args.batch:
            for source in sorted(batch.glob('*_result.json')):
                prefix = source.name.split('_')[0]
                input_path = batch / f'{prefix}_input.json'
                payload = json.loads(input_path.read_text(encoding='utf-8'))
                record = json.loads(source.read_text(encoding='utf-8'))
                origin = source
                if record.get('status') == 'completed':
                    assessment = record['assessment']
                else:
                    origin = batch / f'{prefix}_local_review.json'
                    if not origin.exists():
                        continue
                    assessment = json.loads(origin.read_text(encoding='utf-8'))['assessment']
                identity = (payload['vacancy']['id'], payload['profile']['profile_id'])
                if identity in seen:
                    continue
                seen.add(identity)
                review = apply_policy(assessment, payload['vacancy'], profile_id=identity[1])
                review.update(vacancy_id=identity[0], profile_id=identity[1],
                              source_path=str(source.resolve()), source_sha256=sha(source),
                              input_sha256=sha(input_path), assessment_source_sha256=sha(origin),
                              policy_sha256=policy_hash, original_decision=assessment['decision'],
                              kind='local_policy_replay_not_new_model_answer')
                key = history.save_review(review)
                (output / f'{key}.json').write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding='utf-8')
                cards.extend(render_card(payload, review))
                print(f"{identity[0]} | {identity[1]} | {assessment['decision']} -> {review['assessment']['decision']} / {review['assessment']['delivery']['action']}")
    (output / 'report.md').write_text('\n'.join(['# Сохранённые вакансии: локальный пересчёт', '', *cards]), encoding='utf-8')
    print(f'Карточек: {len(seen)}. Отчёт: {output / "report.md"}. Сеть и ключи не использовались.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
