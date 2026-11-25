#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Статистика файлов по расширениям в папке (рекурсивно).

Используйте этот скрипт, если нужно понять, что же хранится в папке
для бэкапа и какие расширения нужно копировать.

https://github.com/artemsoft2025


Запуск:
    python folder_stats.py
Затем вставьте путь к папке — скрипт пройдёт по всем вложенным
папкам, посчитает количество и размер файлов каждого типа и
откроет интерактивный просмотрщик:

  Таблица:
    ↑/↓ или k/j  — перемещение по строкам
    Enter        — открыть список файлов этого расширения
    Home/g       — в начало, End/G — в конец
    PgUp/PgDn    — постранично
    q            — выход

  Список файлов:
    ↑/↓ или k/j  — прокрутка
    s            — переключить сортировку (размер ↓ / имя ↑)
    q или Esc    — назад в таблицу

Если запуск не из терминала (нет TTY), выводится обычный
текстовый отчёт. Если curses недоступен (например, на Alt Linux
не установлен пакет python3-modules-curses), но терминал есть —
запускается запасное текстовое меню: таблица с номерами, вводите
номер расширения — получаете список файлов этого типа.
"""

import os
import sys
from collections import Counter, defaultdict

try:
    import curses
    _HAS_CURSES = True
    _CURSES_ERR = None
except Exception as e:                   # на урезанных сборках / Alt Linux без пакета curses
    _HAS_CURSES = False
    _CURSES_ERR = e


def get_extension(filename: str) -> str:
    """Возвращает расширение в нижнем регистре с точкой, либо '(без расширения)'."""
    _, ext = os.path.splitext(filename)
    ext = ext.lower()
    return ext if ext else "(без расширения)"


def scan_folder(folder: str):
    """Рекурсивно обходит папку: считает кол-во и размер по расширениям + собирает списки файлов."""
    counts = Counter()
    sizes = Counter()                    # суммарный размер в байтах по расширению
    files_by_ext = defaultdict(list)     # ext -> список (полный_путь, размер_в_байтах)
    total_files = 0
    total_size = 0
    total_dirs = 0
    errors = []

    for root, dirs, files in os.walk(folder):
        total_dirs += len(dirs)
        for name in files:
            full_path = os.path.join(root, name)
            try:
                # считаем только обычные файлы (пропускаем ссылки и пр.)
                if os.path.isfile(full_path):
                    ext = get_extension(name)
                    file_size = os.path.getsize(full_path)
                    counts[ext] += 1
                    sizes[ext] += file_size
                    files_by_ext[ext].append((full_path, file_size))
                    total_files += 1
                    total_size += file_size
            except (OSError, PermissionError) as e:
                errors.append((full_path, str(e)))

    return counts, sizes, files_by_ext, total_files, total_size, total_dirs, errors


def format_size(num_bytes):
    """Человекочитаемый размер."""
    n = float(num_bytes)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


# ------------------------------------------------------------------ текстовый отчёт (fallback)

def print_report(folder, counts, sizes, total_files, total_size, total_dirs, errors):
    print()
    print("=" * 72)
    print(f"Папка: {folder}")
    print("=" * 72)
    print(f"Всего папок (включая вложенные): {total_dirs}")
    print(f"Всего файлов: {total_files}")
    print(f"Общий размер: {format_size(total_size)}")
    print(f"Уникальных расширений: {len(counts)}")
    print("-" * 72)

    if not counts:
        print("Файлы не найдены.")
        return

    max_ext_len = max(len(ext) for ext in counts)
    col_ext = max(max_ext_len, len("Расширение"))

    print(f"{'Расширение':<{col_ext}} | {'Кол-во':>8} | {'Доля':>8} | {'Размер':>12}")
    sep_len = col_ext + 3 + 8 + 3 + 8 + 3 + 12
    print("-" * sep_len)

    for ext, count in counts.most_common():
        share = (count / total_files * 100) if total_files else 0
        size_str = format_size(sizes[ext])
        print(f"{ext:<{col_ext}} | {count:>8} | {share:>7.2f}% | {size_str:>12}")

    print("-" * sep_len)
    print(f"{'ИТОГО':<{col_ext}} | {total_files:>8} | {'100.00%':>8} | {format_size(total_size):>12}")

    if errors:
        print()
        print(f"Внимание: не удалось прочитать {len(errors)} файл(ов).")
        for path, err in errors[:5]:
            print(f"  - {path}: {err}")
        if len(errors) > 5:
            print(f"  ... и ещё {len(errors) - 5}")


# ------------------------------------------------------------------ интерактивный просмотрщик (curses)

def _put(stdscr, y, x, text, attr=0):
    """Безопасный вывод: не падает на последней строке/столбце терминала."""
    try:
        if attr:
            stdscr.addstr(y, x, text, attr)
        else:
            stdscr.addstr(y, x, text)
    except curses.error:
        pass


def _truncate_left(s, width):
    """Обрезает строку слева, оставляя конец (имя файла важнее начала пути)."""
    if width <= 0:
        return ""
    if len(s) <= width:
        return s
    if width <= 3:
        return s[-width:]
    return "..." + s[-(width - 3):]


def _clamp_scroll(selected, top, visible):
    """Держит выбранную строку в видимой области."""
    if selected < top:
        top = selected
    elif selected >= top + visible:
        top = selected - visible + 1
    return max(0, top)


def table_loop(stdscr, data):
    folder, counts, sizes, files_by_ext, total_files, total_size, total_dirs, errors = data
    exts = [ext for ext, _ in counts.most_common()]
    n = len(exts)
    selected = 0
    top = 0

    stdscr.keypad(True)
    curses.curs_set(0)                    # спрятать курсор

    while True:
        stdscr.clear()
        max_y, max_x = stdscr.getmaxyx()

        # --- шапка ---
        _put(stdscr, 0, 0, f"Папка: {folder}"[:max_x - 1])
        _put(stdscr, 1, 0, f"Всего папок: {total_dirs}   Всего файлов: {total_files}"[:max_x - 1])
        _put(stdscr, 2, 0, f"Общий размер: {format_size(total_size)}   "
                           f"Уникальных расширений: {len(counts)}"[:max_x - 1])

        if n == 0:
            _put(stdscr, 4, 0, "Файлы не найдены.")
            _put(stdscr, max_y - 1, 0, "q — выход"[:max_x - 1])
            stdscr.refresh()
            key = stdscr.getch()
            if key in (ord('q'), ord('Q')):
                break
            continue

        header_y = 4
        _put(stdscr, header_y, 0,
             f"{'Расширение':<22} {'Кол-во':>8} {'Доля':>9} {'Размер':>12}"[:max_x - 1])
        _put(stdscr, header_y + 1, 0, "-" * min(max_x - 1, 60))

        rows_start = header_y + 2
        footer_y = max_y - 1
        visible = max(1, footer_y - rows_start)
        top = _clamp_scroll(selected, top, visible)

        for i in range(visible):
            idx = top + i
            if idx >= n:
                break
            ext = exts[idx]
            count = counts[ext]
            share = (count / total_files * 100) if total_files else 0
            size_str = format_size(sizes[ext])
            line = f"{ext:<22} {count:>8} {share:>8.2f}% {size_str:>12}"
            line = line[:max_x - 1]
            y = rows_start + i
            if idx == selected:
                _put(stdscr, y, 0, line.ljust(max_x - 1), curses.A_REVERSE)
            else:
                _put(stdscr, y, 0, line)

        _put(stdscr, footer_y, 0,
             "↑/↓ перемещение · Enter открыть · Home/End · PgUp/PgDn · q выход"[:max_x - 1])
        stdscr.refresh()

        key = stdscr.getch()
        if key in (ord('q'), ord('Q')):
            break
        elif key in (curses.KEY_UP, ord('k')):
            selected = max(0, selected - 1)
        elif key in (curses.KEY_DOWN, ord('j')):
            selected = min(n - 1, selected + 1)
        elif key in (curses.KEY_HOME, ord('g')):
            selected = 0
        elif key in (curses.KEY_END, ord('G')):
            selected = n - 1
        elif key == curses.KEY_PPAGE:
            selected = max(0, selected - visible)
        elif key == curses.KEY_NPAGE:
            selected = min(n - 1, selected + visible)
        elif key in (curses.KEY_ENTER, 10, 13):
            detail_loop(stdscr, exts[selected], files_by_ext[exts[selected]], sizes[exts[selected]])
        # KEY_RESIZE — просто перерисуем на следующей итерации


def detail_loop(stdscr, ext, file_list, total_bytes):
    n = len(file_list)
    sort_by_size = True
    files = sorted(file_list, key=lambda x: x[1], reverse=True)   # размер ↓ по умолчанию
    selected = 0
    top = 0

    stdscr.keypad(True)

    while True:
        stdscr.clear()
        max_y, max_x = stdscr.getmaxyx()

        _put(stdscr, 0, 0, f"Расширение: {ext}"[:max_x - 1])
        _put(stdscr, 1, 0,
             f"Файлов: {n}   Размер: {format_size(total_bytes)}   "
             f"сортировка: {'размер ↓' if sort_by_size else 'имя ↑'}"[:max_x - 1])
        _put(stdscr, 2, 0, "-" * min(max_x - 1, 60))

        rows_start = 3
        footer_y = max_y - 1
        status_y = max_y - 2
        visible = max(1, status_y - rows_start)
        top = _clamp_scroll(selected, top, visible)

        size_w = 12
        path_w = max(8, max_x - size_w - 2)

        for i in range(visible):
            idx = top + i
            if idx >= n:
                break
            path, size = files[idx]
            disp_path = _truncate_left(path, path_w)
            line = f"{disp_path:<{path_w}} {format_size(size):>12}"
            line = line[:max_x - 1]
            y = rows_start + i
            if idx == selected:
                _put(stdscr, y, 0, line.ljust(max_x - 1), curses.A_REVERSE)
            else:
                _put(stdscr, y, 0, line)

        # строка статуса: полный путь выбранного файла (в таблице он обрезан)
        if n > 0:
            sel_path = files[selected][0]
            _put(stdscr, status_y, 0, _truncate_left(sel_path, max_x - 1))

        _put(stdscr, footer_y, 0,
             f"↑/↓ прокрутка · s сортировка · q/Esc назад   [{selected + 1}/{n}]"[:max_x - 1])
        stdscr.refresh()

        key = stdscr.getch()
        if key in (ord('q'), ord('Q'), 27):                       # 27 = Esc
            break
        elif key in (curses.KEY_UP, ord('k')):
            selected = max(0, selected - 1)
        elif key in (curses.KEY_DOWN, ord('j')):
            selected = min(n - 1, selected + 1)
        elif key in (curses.KEY_HOME, ord('g')):
            selected = 0
        elif key in (curses.KEY_END, ord('G')):
            selected = n - 1
        elif key == curses.KEY_PPAGE:
            selected = max(0, selected - visible)
        elif key == curses.KEY_NPAGE:
            selected = min(n - 1, selected + visible)
        elif key in (ord('s'), ord('S')):
            sort_by_size = not sort_by_size
            files = (sorted(files, key=lambda x: x[1], reverse=True) if sort_by_size
                     else sorted(files, key=lambda x: x[0]))
            selected = 0
            top = 0


def interactive_main(data):
    curses.wrapper(table_loop, data)


# ------------------------------------------------------------------ запасное текстовое меню (без curses)

PAGE_SIZE = 20


def show_file_list_text(ext, file_list, total_bytes):
    """Печатает список файлов расширения постранично (сортировка по размеру ↓)."""
    files = sorted(file_list, key=lambda x: x[1], reverse=True)
    n = len(files)
    print()
    print(f"Расширение: {ext}    Файлов: {n}    Размер: {format_size(total_bytes)}")
    print("-" * 72)
    start = 0
    while start < n:
        for i in range(start, min(start + PAGE_SIZE, n)):
            path, size = files[i]
            print(f"{i + 1:>4}  {format_size(size):>10}  {path}")
        start += PAGE_SIZE
        if start < n:
            ans = input(f"\n[Enter] далее  ·  q — назад к таблице  ({start}/{n}): ").strip()
            if ans.lower() == "q":
                return
        else:
            input("\n[Enter] — назад к таблице: ")


def interactive_text(data):
    """Текстовое меню: показывает таблицу с номерами, по номеру открывает список файлов."""
    folder, counts, sizes, files_by_ext, total_files, total_size, total_dirs, errors = data
    exts = [ext for ext, _ in counts.most_common()]

    while True:
        print()
        print("=" * 72)
        print(f"Папка: {folder}")
        print("=" * 72)
        print(f"Всего папок: {total_dirs}   Всего файлов: {total_files}   "
              f"Общий размер: {format_size(total_size)}")
        print("-" * 72)
        print(f"{'№':>3}  {'Расширение':<22} {'Кол-во':>8} {'Доля':>8} {'Размер':>12}")
        print("-" * 72)

        for i, ext in enumerate(exts):
            count = counts[ext]
            share = (count / total_files * 100) if total_files else 0
            print(f"{i + 1:>3}  {ext:<22} {count:>8} {share:>7.2f}% "
                  f"{format_size(sizes[ext]):>12}")

        print("-" * 72)
        if errors:
            print(f"(не удалось прочитать {len(errors)} файл(ов))")

        raw = input("\nВведите № расширения для списка файлов  ·  q — выход: ").strip()
        if raw == "" or raw.lower() in ("q", "quit", "exit"):
            break
        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(exts):
                show_file_list_text(exts[idx], files_by_ext[exts[idx]], sizes[exts[idx]])
            else:
                print(f"Нет такого номера (всего {len(exts)}). Нажмите Enter.")
                input()
            continue
        print("Нужно число или q. Нажмите Enter.")
        input()


# ------------------------------------------------------------------ точка входа

def main():
    print("Статистика файлов по расширениям (рекурсивно).")
    raw = input("Введите путь к папке: ").strip()

    if not raw:
        print("Путь не указан. Выход.")
        sys.exit(1)

    # убираем кавычки, если пользователь вставил путь в кавычках
    if (raw.startswith('"') and raw.endswith('"')) or \
       (raw.startswith("'") and raw.endswith("'")):
        raw = raw[1:-1]

    folder = os.path.expanduser(raw)

    if not os.path.exists(folder):
        print(f"Путь не существует: {folder}")
        sys.exit(1)
    if not os.path.isdir(folder):
        print(f"Это не папка: {folder}")
        sys.exit(1)

    counts, sizes, files_by_ext, total_files, total_size, total_dirs, errors = scan_folder(folder)

    data = (folder, counts, sizes, files_by_ext, total_files, total_size, total_dirs, errors)
    is_tty = sys.stdin.isatty() and sys.stdout.isatty()

    # ---- выбор режима: curses → текстовое меню → текстовый отчёт ----
    if _HAS_CURSES and is_tty:
        # полноценный интерактивный просмотрщик
        try:
            interactive_main(data)
            return
        except Exception as e:
            print(f"curses не запустился ({e}); переключаюсь на текстовое меню.")

    if is_tty:
        # запасной интерактивный режим без curses
        if not _HAS_CURSES:
            print()
            print(f"Модуль curses недоступен в этом Python "
                  f"({type(_CURSES_ERR).__name__}: {_CURSES_ERR}).")
            print("Используется текстовое меню: вводите номер расширения — получите список файлов.")
            print("Чтобы включить полноценный curses-интерфейс, установите пакет curses:")
            print("    ALT Linux:  apt-get install python3-modules-curses")
            print("               (если имя другое — найдите: apt-cache search curses)")
            print()
        try:
            interactive_text(data)
            return
        except (KeyboardInterrupt, EOFError):
            print()
            return

    # запуск не из терминала (нет TTY) — обычный текстовый отчёт
    print_report(folder, counts, sizes, total_files, total_size, total_dirs, errors)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nПрервано пользователем.")
        sys.exit(130)
