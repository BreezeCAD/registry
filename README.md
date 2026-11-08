# Каталог модулей и библиотек BreezeCAD

Здесь собирается **`index.json`** — список всех модулей и библиотек для
[BreezeCAD](https://github.com/BreezeCAD/breezecad). По нему работает раздел
[«Модули и библиотеки»](https://breezecad.ru/modules.html) на сайте, а потом будет
работать вкладка «Каталог» в самой программе (ADR-0005 основного репозитория).

Своего сервера нет: всё лежит на GitHub. Файлы модулей остаются в выпусках
репозиториев авторов, каталог хранит только ссылки на них.

*English summary at the bottom.*

## Как это устроено

```
репозиторий модуля                     BreezeCAD/registry                    breezecad.ru
breezecad.json + выпуск с файлами  →   build-index (раз в сутки,       →     data/registry-index.json
(тема breezecad-module / -library)     по событию, вручную) → index.json     → раздел «Модули и библиотеки»
```

1. В корне репозитория модуля или библиотеки лежит паспорт **`breezecad.json`**.
2. Action `build-index` раз в сутки (и по событию `repository_dispatch`) обходит:
   - репозитории организации **BreezeCAD** с темой `breezecad-module` или `breezecad-library`;
   - внешние репозитории из **`external.json`**;
   - паспорта в папке **`entries/`**: так описано то, что живёт не в своём репозитории
     (языковые пакеты, встроенные пакеты изделий).
3. Каждый паспорт проверяется по схеме [`schema/breezecad.schema.json`](schema/breezecad.schema.json).
   Затем каталог находит в выпуске нужные файлы и записывает в `index.json` версию,
   ссылки, размеры и платформы.
4. Если каталог изменился, Action коммитит его и просит сайт обновиться.

Битый паспорт не ломает каталог: он попадает в список `errors` в `index.json` и в
предупреждения Action, остальные записи публикуются как обычно.

## Автору: как попасть в каталог

### 1. Паспорт `breezecad.json`

```json
{
  "$schema": "https://raw.githubusercontent.com/BreezeCAD/registry/main/schema/breezecad.schema.json",
  "schemaVersion": 1,
  "type": "library",
  "id": "diy-motion",
  "name": {
    "ru": "DIY: двигатели, направляющие, линейные подшипники, передачи",
    "en": "DIY: motors, linear guides, linear bearings, drives"
  },
  "author": { "ru": "Верхолашин М. В.", "en": "M. V. Verkholashin", "github": "MikeVerx" },
  "description": {
    "ru": "Шаговые NEMA 8–34, рельсы и каретки MGN, валы, LM…UU, LMF…UU, ходовые винты Tr, гайки и кулачковые муфты.",
    "en": "NEMA 8–34 steppers, MGN rails and blocks, shafts, LM…UU, LMF…UU, Tr lead screws, nuts and jaw couplings."
  },
  "tags": ["3d-печать", "чпу", "двигатели", "направляющие"],
  "minBreezeCAD": "0.2.5.1",
  "license": "MPL-2.0",
  "download": { "release": "latest", "assets": ["diy-motion.bzlib"] }
}
```

| Поле | Обязательно | Что это |
|---|---|---|
| `schemaVersion` | да | всегда `1` |
| `type` | да | `module` — модуль (`.bzmod`); `library` — библиотека изделий (`.bzlib`) и другие данные |
| `id` | да | латиница, цифры, `.`, `-`, `_`, 2–64 знака; тот же, что в `module.json` или в поле `id` пакета `.bzlib`. Уникален во всём каталоге |
| `name` | да | название, `ru` и `en` |
| `author` | да | автор, `ru` и `en`; по нему работает фильтр на сайте. `github` — ник, необязательно |
| `description` | да | одно-два предложения, `ru` и `en`, до 400 знаков |
| `tags` | нет | до 12 тегов строчными буквами |
| `minBreezeCAD` | да | самая старая версия BreezeCAD, где это работает: `0.2.5` или `0.2.5.1` |
| `license` | нет | например `MPL-2.0`, `MIT`, `Proprietary` |
| `homepage` | нет | страница с описанием (https) |
| `bundled` | нет | `true`, если уже встроено в программу |
| `download` | да | откуда брать файлы — см. ниже |

**`download`, вариант 1 — из выпуска GitHub (рекомендуем):**

```json
"download": { "release": "latest", "assets": ["bz-mymod-*.bzmod"] }
```

- `release` — `latest` (последний выпуск, пре-релизы не считаются) или конкретный тег;
- `assets` — имена файлов выпуска, можно с `*` и `?`;
- `repo` — `owner/name`, если файлы лежат в другом репозитории (по умолчанию — тот, где паспорт).

Версия в каталоге берётся из тега выпуска (`v1.2.0` → `1.2.0`). Платформу каталог
определяет по имени файла: `windows`, `linux`, `macos`, `android`, `ios` (`.exe`, `.dmg`,
`.apk`, `.ipa` тоже узнаются), иначе — «любая». Для модулей держитесь имён из основного
репозитория: `bz-<id>-<версия>-<система>-<архитектура>.bzmod`.

**`download`, вариант 2 — прямые ссылки:**

```json
"download": {
  "version": "1.0",
  "urls": [ { "url": "https://example.com/my.bzlib", "name": "my.bzlib", "platform": "any" } ]
}
```

Проверить паспорт до публикации:

```
pip install jsonschema
python3 -c "import json,jsonschema; jsonschema.validate(json.load(open('breezecad.json')), json.load(open('breezecad.schema.json')))"
```

### 2а. Репозиторий в организации BreezeCAD

1. Положите `breezecad.json` в корень и выпустите релиз с файлами.
2. Добавьте репозиторию тему (**About → Topics**): `breezecad-module` или `breezecad-library`.
   Тема должна совпадать с `type` в паспорте.
3. Всё. Каталог подхватит репозиторий при следующей сборке (раз в сутки) или сразу,
   если запустить `build-index` вручную или прислать событие (ниже).

### 2б. Свой репозиторий вне организации

1. Положите `breezecad.json` в корень публичного репозитория, выпустите релиз.
2. Пришлите PR в этот репозиторий: одна строка в `external.json`:
   ```json
   { "repos": [ { "repo": "your-name/bz-module-something" } ] }
   ```
3. Проверка PR (`check`) убедится, что паспорт читается и файлы находятся. После слияния
   модуль появится в каталоге.

### 3. Обновления

Новая версия — это просто новый выпуск в вашем репозитории: каталог найдёт его сам в
течение суток. Чтобы сразу, добавьте в CI выпуска шаг (нужен токен с правом
`Contents: write` на `BreezeCAD/registry` в секрете `BZ_DISPATCH_TOKEN`):

```yaml
- name: Обновить каталог BreezeCAD
  env:
    TOKEN: ${{ secrets.BZ_DISPATCH_TOKEN }}
  run: |
    [ -n "$TOKEN" ] || exit 0
    curl -fsS -X POST -H "Authorization: Bearer $TOKEN" \
      -H "Accept: application/vnd.github+json" \
      https://api.github.com/repos/BreezeCAD/registry/dispatches \
      -d '{"event_type":"module-released"}'
```

Для внешних авторов этот токен не выдаётся. Ваша новая версия попадёт в каталог при
ежесуточной сборке.

## `index.json`

```json
{
  "schemaVersion": 1,
  "generated": "2026-11-08T03:17:00Z",
  "items": [
    {
      "type": "library", "id": "diy-motion",
      "name": {"ru": "…", "en": "…"}, "author": {"ru": "…", "en": "…"},
      "description": {"ru": "…", "en": "…"}, "tags": ["…"],
      "minBreezeCAD": "0.2.5.1", "license": "MPL-2.0", "bundled": false,
      "version": "1.0.0", "published": "2026-11-08",
      "files": [ {"name": "diy-motion.bzlib", "url": "https://…", "size": 157070, "platform": "any"} ],
      "source": {"name": "BreezeCAD/bz-library-diy-motion", "repo": "BreezeCAD/bz-library-diy-motion", "url": "https://github.com/…"}
    }
  ],
  "errors": [ {"source": "…", "message": "…"} ]
}
```

Если id встречается и в репозитории, и в `entries/`, побеждает паспорт из репозитория.
Так запись из `entries/` можно спокойно заменить настоящим паспортом, когда модуль
переедет в свой репозиторий.

## Для сопровождающих

| Файл | Что |
|---|---|
| `schema/breezecad.schema.json` | схема паспорта (JSON Schema 2020-12) |
| `entries/*.json` | паспорта без своего репозитория |
| `external.json` | внешние репозитории |
| `scripts/build_index.py` | сборщик: `python3 scripts/build_index.py` (нужен `jsonschema`); `--check` — проверка без сети; `--offline` — только `entries/` |
| `.github/workflows/build-index.yml` | сборка: раз в сутки, `repository_dispatch` (`module-released`, `library-released`, `breezecad-released`, `rebuild`), вручную, при правке |
| `.github/workflows/check.yml` | проверка PR |
| `index.json` | результат, его правит только Action |

Секрет **`BZ_DISPATCH_TOKEN`** (fine-grained PAT, `Contents: write` на `BreezeCAD/breezecad-site`)
нужен, чтобы после изменения каталога сайт обновлялся сразу. Без него сайт обновится
сам раз в сутки.

---

## English summary

This repository builds **`index.json`**, the catalog of BreezeCAD modules and libraries
used by breezecad.ru and, later, by the in-app catalog. To get listed:

1. Put a **`breezecad.json`** passport in the root of your repository (schema:
   `schema/breezecad.schema.json`; all user-facing texts in `ru` and `en`) and publish
   a GitHub release with your files.
2. Inside the BreezeCAD organization: add the topic `breezecad-module` or
   `breezecad-library`. Outside it: open a PR adding your repository to `external.json`.
3. The catalog is rebuilt daily (and on `repository_dispatch`). New releases are
   picked up automatically.
