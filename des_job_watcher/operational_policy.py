"""Версионированный дополнительный фильтр. Ответ модели не изменяется."""

from copy import deepcopy
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def load_policy():
    return json.loads((ROOT / 'config/operational_policy.json').read_text(encoding='utf-8'))


def equipment_barriers(description):
    """Консервативно распознать явное требование оборудования, вернуть цитаты."""
    found = []
    for line in re.split(r'[\n;.!?]+', description):
        line = line.strip(' \t—-•')
        lower = line.lower().replace('ё', 'е')
        if not re.search(r'\b(гарнитур\w*|микрофон\w*|(?:веб[- ]?)?камер\w*)\b', lower):
            continue
        if re.search(r'\bне\s+(?:нуж\w*|требу\w*|обязател\w*|использ\w*)|без\s+(?:гарнитур|микрофон|камер)', lower):
            continue
        # Камеры наблюдения/аннотирование изображений не означают оборудование кандидата.
        if re.search(r'наблюдени|видеонаблюдени|изображени|разметк|ремонт|продаж', lower):
            continue
        requirement = re.search(r'\b(?:необходим\w*|потребу\w*|понадоб\w*|требу\w*|наличи\w*|иметь|нуж\w*|обязател\w*)\b', lower)
        equipment_item = re.match(r'^(?:гарнитура|микрофон|(?:веб[- ]?)?камера)\b', lower)
        if requirement or equipment_item:
            found.append(line)
    return found


def apply_policy(assessment, vacancy):
    result = deepcopy(assessment)
    quotes = equipment_barriers(vacancy['description'])
    overrides = []
    if quotes:
        result['decision'] = 'unsuitable'
        result['delivery'] = {'action': 'exclude', 'reasons': ['required_communication_equipment']}
        overrides.append({'rule': 'required_communication_equipment', 'quotes': quotes})
    return {'operational_policy_version': load_policy()['version'],
            'assessment': result, 'overrides': overrides}


def add_workplace_evidence(payload, path=None):
    """Локальные факты владельца только для личного запуска, не учебных профилей."""
    path = Path(path) if path else ROOT / 'data/private/workplace.json'
    result = deepcopy(payload)
    if result['profile'].get('profile_kind') == 'synthetic' or not path.exists():
        return result
    context = json.loads(path.read_text(encoding='utf-8'))
    prefix = result['profile']['profile_id']
    for item in context['facts']:
        result['profile']['evidence'].append({
            'id': f"{prefix}_workplace_{item['id']}", 'fact': item['fact'],
            'period': 'Подтверждено владельцем 2026-10-29',
            'context': 'Локальный контекст рабочего места; не сведения об опыте из резюме.',
        })
    result['workplace_context_version'] = context['version']
    return result
