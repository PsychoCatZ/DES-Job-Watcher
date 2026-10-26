"""Сборка переносимого запроса анализа без вызова внешних сервисов."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROMPT_VERSION = 4


def canonical_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def fingerprint(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def build_request(payload):
    """Отделить доверенные инструкции от данных и сохранить их отпечатки."""
    rules = json.loads((ROOT / 'config' / 'matching_rules.json').read_text(encoding='utf-8'))
    schema = json.loads((ROOT / 'config' / 'analysis_response.schema.json').read_text(encoding='utf-8'))
    instruction = (ROOT / 'prompts' / f'assessment_v{PROMPT_VERSION}.txt').read_text(encoding='utf-8').strip()
    if not isinstance(payload, dict) or payload.get('input_version') != 1:
        raise ValueError('Неизвестный формат входа анализа.')
    if payload.get('rules') != rules:
        raise ValueError('Правила входа устарели или отличаются от текущих. Пересоберите вход.')
    try:
        profile = payload['profile']
        vacancy = payload['vacancy']
        if not isinstance(profile, dict) or profile['profile_id'] not in ('support', 'developer', 'ai_data'):
            raise ValueError('Неизвестный профиль.')
        if type(profile['version']) is not int or profile['version'] < 1:
            raise ValueError('Неверная версия профиля.')
        if not isinstance(profile['evidence'], list) or not profile['evidence']:
            raise ValueError('Профиль не содержит оснований.')
        if not isinstance(vacancy, dict) or any(
            not isinstance(vacancy.get(key), str) or not vacancy[key].strip()
            for key in ('id', 'name', 'description')
        ):
            raise ValueError('Нужны ID, название и полное описание вакансии.')
    except (KeyError, TypeError) as error:
        raise ValueError('Неполный вход анализа.') from error

    # Явный список полей не пропускает локальные пути и служебные метаданные.
    profile_fields = ('profile_id', 'version', 'label', 'evidence_note', 'target_tasks',
                      'working_method', 'evidence', 'education', 'boundaries')
    vacancy_fields = ('id', 'name', 'employer', 'description', 'work_formats', 'archived')
    data = {
        'profile': {key: profile[key] for key in profile_fields if key in profile},
        'vacancy': {key: vacancy[key] for key in vacancy_fields if key in vacancy},
    }
    user_content = canonical_json(data)
    system_content = (instruction + '\n\nДОВЕРЕННЫЕ ПРАВИЛА:\n' + canonical_json(rules)
                      + '\n\nКОНТРАКТ ОТВЕТА:\n' + canonical_json(schema))
    messages = [{'role': 'system', 'content': system_content},
                {'role': 'user', 'content': user_content}]
    return {
        'request_version': 1, 'prompt_version': PROMPT_VERSION,
        'rules_version': rules['version'],
        'input_sha256': fingerprint(user_content),
        'instructions_sha256': fingerprint(system_content),
        'request_sha256': fingerprint(canonical_json(messages)),
        'messages': messages,
    }
