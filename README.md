# i18n-claim-audit

An offline static audit of documented language-support promises.
Python >=3.9, standard library runtime, version 0.1.0, MIT licensed.

```sh
pip install i18n-claim-audit
i18n-claim-audit . --json
python3 -m i18n_claim_audit . --verbose
```

The scanner reads root README.md and Markdown files under any docs directory.
Fenced blocks are excluded, inline code counts, and wrapped paragraph lines are
joined. Matching normalizes case, hyphens, and whitespace and uses word boundaries.
Negative phrase spans are removed before positive matching.

Evidence consists of paired gettext imports and calls, Babel or Fluent calls,
Qt translator construction and installation, PO/MO catalogs, or JSON objects with
string values at the top level or one object level down beneath locale, locales,
lang, langs, i18n, or translations directories. Source and catalogs under tests
and test_*.py files are excluded. Imports alone, encoding operations, locale
configuration, and arbitrary dictionaries do not establish evidence. Source is
parsed, never executed. Static evidence cannot guarantee runtime correctness or
catalog completeness. Dynamic imports and runtime rebinding are outside scope.

```text
documented-i18n-claim-false HIGH
documented-no-i18n-claim-false HIGH
```

One finding is emitted per contradicted family. Regular documents take precedence
over tests documents; claims found only under tests receive MEDIUM severity.
No claim yields PASS. JSON contains status, evidence, claims, and findings;
each finding contains rule, severity, and path. Status reflects findings even
when the selected threshold permits exit 0.

```text
i18n-claim-audit [ROOT] [--json] [--verbose] [--ignore GLOB ...]
                 [--fail-on HIGH|MEDIUM] [--version]
```

ROOT defaults to the current directory. Ignore patterns use fnmatch on POSIX
relative paths; matching directories exclude descendants. Symlinks are skipped.
Environment dotfiles are never opened. Exit 0 means no findings at the selected
threshold, 2 means findings at that threshold, and 1 means usage or input errors.
The default threshold is MEDIUM. Text output starts with PASS/FAIL followed by
rule and severity per finding; verbose mode adds paths.

Run tests with `python3 -m unittest discover`. Build with `python3 -m build`.

Recognized phrase templates:

```text
I18N:
supports multiple languages
multiple languages supported
multiple language support
available in multiple languages
supports several languages
supports many languages
supports other languages
supports translations
translation support
translations supported
translations available
translation system
supports translation
localized
localised
localization support
localisation support
internationalization support
internationalisation support
i18n support
supports i18n
multilingual support
is multilingual
fully translated
translated into multiple languages

NOI18N:
no translation support
no translations
does not support translations
does not support translation
not translated
never translated
does not support multiple languages
no localization support
no localisation support
no i18n support
does not support i18n
not localized
not localised
no multilingual support
not multilingual
english only
only available in english
available in english only
english only support
```
