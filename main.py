"""Порівняння трьох алгоритмів пошуку підрядка за допомогою timeit.

Запуск: python main.py
Лише перевірка правильності: python main.py --check-only
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import random
import statistics
import timeit


BASE_DIR = Path(__file__).resolve().parent
ABSENT_PATTERN = "Цей вигаданий підрядок відсутній у статті."
ARTICLES = (
    ("article_1.txt", "інтерполяції. Найефективніше застосовувати"),
    ("article_2.txt", "при традиційних представленнях структур не"),
)


def _good_suffix_shifts(pattern: str) -> list[int]:
    """Таблиця зсувів за правилом доброго суфікса за O(m)."""
    size = len(pattern)
    shifts = [0] * (size + 1)
    borders = [0] * (size + 1)
    i, j = size, size + 1
    borders[i] = j
    while i > 0:
        while j <= size and pattern[i - 1] != pattern[j - 1]:
            if shifts[j] == 0:
                shifts[j] = j - i
            j = borders[j]
        i -= 1
        j -= 1
        borders[i] = j

    j = borders[0]
    for i in range(size + 1):
        if shifts[i] == 0:
            shifts[i] = j
        if i == j:
            j = borders[j]
    return shifts


def boyer_moore_search(text: str, pattern: str) -> int:
    """Боєр–Мур: правила поганого символу та доброго суфікса."""
    n, m = len(text), len(pattern)
    if m == 0:
        return 0
    if m > n:
        return -1
    last_occurrence = {character: i for i, character in enumerate(pattern)}
    good_suffix = _good_suffix_shifts(pattern)
    start = 0
    while start <= n - m:
        j = m - 1
        while j >= 0 and pattern[j] == text[start + j]:
            j -= 1
        if j < 0:
            return start
        bad_character = j - last_occurrence.get(text[start + j], -1)
        start += max(1, bad_character, good_suffix[j + 1])
    return -1


def _prefix_table(pattern: str) -> list[int]:
    """Довжини найбільших власних префіксів, що є суфіксами."""
    prefix = [0] * len(pattern)
    matched = 0
    for i in range(1, len(pattern)):
        while matched and pattern[i] != pattern[matched]:
            matched = prefix[matched - 1]
        if pattern[i] == pattern[matched]:
            matched += 1
        prefix[i] = matched
    return prefix


def kmp_search(text: str, pattern: str) -> int:
    """Кнут–Морріс–Пратт: перший збіг або -1."""
    n, m = len(text), len(pattern)
    if m == 0:
        return 0
    if m > n:
        return -1
    prefix = _prefix_table(pattern)
    matched = 0
    for i, character in enumerate(text):
        while matched and character != pattern[matched]:
            matched = prefix[matched - 1]
        if character == pattern[matched]:
            matched += 1
        if matched == m:
            return i - m + 1
    return -1


def rabin_karp_search(text: str, pattern: str) -> int:
    """Рабін–Карп: ковзний хеш і точна перевірка при збігу хешів."""
    n, m = len(text), len(pattern)
    if m == 0:
        return 0
    if m > n:
        return -1
    base, modulus = 256, 1_000_000_007
    highest_power = pow(base, m - 1, modulus)
    pattern_hash = window_hash = 0
    for i in range(m):
        pattern_hash = (pattern_hash * base + ord(pattern[i])) % modulus
        window_hash = (window_hash * base + ord(text[i])) % modulus

    for start in range(n - m + 1):
        if window_hash == pattern_hash and text[start:start + m] == pattern:
            return start
        if start < n - m:
            window_hash = (
                (window_hash - ord(text[start]) * highest_power) * base
                + ord(text[start + m])
            ) % modulus
    return -1


ALGORITHMS = {
    "Боєр–Мур": boyer_moore_search,
    "Кнут–Морріс–Пратт": kmp_search,
    "Рабін–Карп": rabin_karp_search,
}


def load_articles() -> list[dict]:
    articles = []
    for filename, present_pattern in ARTICLES:
        path = BASE_DIR / filename
        data = path.read_bytes()
        text = data.decode("utf-8")
        if text.find(present_pattern) < 0:
            raise ValueError(f"{filename}: наявний підрядок не знайдено")
        if ABSENT_PATTERN in text:
            raise ValueError(f"{filename}: вигаданий підрядок насправді існує")
        if len(present_pattern) != len(ABSENT_PATTERN):
            raise ValueError("Для порівняння потрібні підрядки однакової довжини")
        articles.append({
            "filename": filename,
            "text": text,
            "characters": len(text),
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "present_pattern": present_pattern,
        })
    return articles


def check_correctness(articles: list[dict]) -> int:
    """Крайові випадки, випадкові рядки й реальні статті проти str.find."""
    cases = [
        ("", ""), ("", "a"), ("abc", ""), ("abc", "abcd"),
        ("abc", "abc"), ("abc", "a"), ("abc", "c"), ("abc", "z"),
        ("aaaaaa", "aaa"), ("abababab", "ababa"),
        ("abcabcabcd", "abcabcd"), ("aaaaab", "aaab"),
        ("Україна — це Україна", "Україна"), ("їєґ🙂ї", "🙂ї"),
        ("рядок\nще рядок", "\nще"),
        # Обидва двосимвольні рядки мають однаковий хеш з основою 256.
        ("\u0001\u0000", "\u0000\u0100"),
    ]
    rng = random.Random(20261107)
    alphabet = "aaabбвіїєґ🙂 \n"
    for _ in range(1000):
        text = "".join(rng.choices(alphabet, k=rng.randrange(101)))
        if rng.randrange(2):
            start = rng.randrange(len(text) + 1)
            pattern = text[start:start + rng.randrange(25)]
        else:
            pattern = "".join(rng.choices(alphabet, k=rng.randrange(25)))
        cases.append((text, pattern))
    for article in articles:
        cases.extend((article["text"], pattern) for pattern in (
            article["present_pattern"], ABSENT_PATTERN,
        ))

    checks = 0
    for text, pattern in cases:
        expected = text.find(pattern)
        for name, function in ALGORITHMS.items():
            actual = function(text, pattern)
            if actual != expected:
                raise AssertionError(
                    f"{name}: {text!r}, {pattern!r}: {actual} != {expected}"
                )
            checks += 1
    return checks


def benchmark(articles: list[dict], number: int, repeat: int) -> dict:
    results = []
    jobs = [
        (article, kind, pattern, name, function)
        for article in articles
        for kind, pattern in (
            ("наявний", article["present_pattern"]),
            ("відсутній", ABSENT_PATTERN),
        )
        for name, function in ALGORITHMS.items()
    ]
    # Детермінований змішаний порядок зменшує вплив порядку виконання.
    random.Random(5).shuffle(jobs)
    for article, kind, pattern, name, function in jobs:
        text = article["text"]
        for _ in range(3):
            function(text, pattern)
        # Зчитування файлів, перевірки й друк не входять у вимірювання.
        # Побудова таблиць / початкових хешів входить у кожний виклик.
        samples = timeit.repeat(
            lambda: function(text, pattern), number=number, repeat=repeat,
        )
        per_call = [sample / number for sample in samples]
        results.append({
            "article": article["filename"],
            "kind": kind,
            "pattern": pattern,
            "pattern_length": len(pattern),
            "index": text.find(pattern),
            "algorithm": name,
            "batch_seconds": samples,
            "median_seconds": statistics.median(per_call),
            "min_seconds": min(per_call),
            "max_seconds": max(per_call),
        })
    results.sort(key=lambda row: (
        row["article"], row["kind"] != "наявний",
        list(ALGORITHMS).index(row["algorithm"]),
    ))
    return {
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "environment": {
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "os": platform.platform(),
            "processor": platform.processor(),
        },
        "number": number,
        "repeat": repeat,
        "warmup_calls_per_case": 3,
        "metric": "median(batch_seconds / number)",
        "articles": [{k: v for k, v in article.items() if k != "text"}
                     for article in articles],
        "results": results,
    }


def print_results(report: dict) -> None:
    print("\nЧас одного пошуку, мкс (медіана / мінімум / максимум):")
    for row in report["results"]:
        times = " / ".join(f"{row[key] * 1e6:.3f}" for key in (
            "median_seconds", "min_seconds", "max_seconds",
        ))
        print(f"{row['article']} | {row['kind']:9} | "
              f"{row['algorithm']:18} | {times}")
    for article in [item["filename"] for item in report["articles"]] + [None]:
        totals = {
            name: sum(row["median_seconds"] for row in report["results"]
                      if row["algorithm"] == name
                      and (article is None or row["article"] == article))
            for name in ALGORITHMS
        }
        winner = min(totals, key=totals.get)
        label = article or "Обидві статті разом"
        print(f"{label}: найшвидший — {winner}; "
              f"сума медіан = {totals[winner] * 1e6:.3f} мкс")


def positive_int(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("значення має бути більше нуля")
    return number


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--number", type=positive_int, default=200,
                        help="пошуків у кожній серії (типово 200)")
    parser.add_argument("--repeat", type=positive_int, default=7,
                        help="кількість серій (типово 7)")
    parser.add_argument("--check-only", action="store_true",
                        help="виконати лише перевірки правильності")
    parser.add_argument("--output", type=Path,
                        help="зберегти заміри у JSON за вказаним шляхом")
    args = parser.parse_args()
    try:
        articles = load_articles()
    except (OSError, UnicodeError, ValueError) as error:
        parser.exit(1, f"Помилка читання статей: {error}\n")
    checks = check_correctness(articles)
    print(f"Перевірки правильності пройдено: {checks}.")
    if args.check_only:
        return
    report = benchmark(articles, args.number, args.repeat)
    report["correctness_checks"] = checks
    print_results(report)
    if args.output:
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"\nРезультати збережено: {args.output}")


if __name__ == "__main__":
    main()
