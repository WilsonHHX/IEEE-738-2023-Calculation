from contextlib import redirect_stdout
from pathlib import Path
import argparse
import ctypes
import io
import sys
import traceback

import matplotlib

matplotlib.use("Agg")

from examples import run_drake

AUTHOR_LINE = "Author: Haixiang Huang"


def default_output_dir(input_csv: Path) -> Path:
    return input_csv.with_name(f"{input_csv.stem}_results")


def run_from_csv(input_csv: Path, output_dir: Path | None = None) -> Path:
    input_csv = input_csv.resolve()
    if output_dir is None:
        output_dir = default_output_dir(input_csv)
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    previous_output_dir = run_drake.OUTPUT_DIR
    previous_argv = sys.argv[:]
    buffer = io.StringIO()

    try:
        run_drake.OUTPUT_DIR = output_dir
        sys.argv = ["run_drake.py", "--input-csv", str(input_csv)]
        with redirect_stdout(buffer):
            run_drake.main()
    finally:
        run_drake.OUTPUT_DIR = previous_output_dir
        sys.argv = previous_argv

    report_path = output_dir / "calculation_report.txt"
    report = (
        f"{AUTHOR_LINE}\n"
        "License: MIT License\n"
        "\n"
        f"{buffer.getvalue()}"
    )
    report_path.write_text(report, encoding="utf-8")
    return report_path


def select_csv_file() -> Path | None:
    class OpenFileName(ctypes.Structure):
        _fields_ = [
            ("lStructSize", ctypes.c_uint32),
            ("hwndOwner", ctypes.c_void_p),
            ("hInstance", ctypes.c_void_p),
            ("lpstrFilter", ctypes.c_wchar_p),
            ("lpstrCustomFilter", ctypes.c_wchar_p),
            ("nMaxCustFilter", ctypes.c_uint32),
            ("nFilterIndex", ctypes.c_uint32),
            ("lpstrFile", ctypes.c_wchar_p),
            ("nMaxFile", ctypes.c_uint32),
            ("lpstrFileTitle", ctypes.c_wchar_p),
            ("nMaxFileTitle", ctypes.c_uint32),
            ("lpstrInitialDir", ctypes.c_wchar_p),
            ("lpstrTitle", ctypes.c_wchar_p),
            ("Flags", ctypes.c_uint32),
            ("nFileOffset", ctypes.c_uint16),
            ("nFileExtension", ctypes.c_uint16),
            ("lpstrDefExt", ctypes.c_wchar_p),
            ("lCustData", ctypes.c_void_p),
            ("lpfnHook", ctypes.c_void_p),
            ("lpTemplateName", ctypes.c_wchar_p),
            ("pvReserved", ctypes.c_void_p),
            ("dwReserved", ctypes.c_uint32),
            ("FlagsEx", ctypes.c_uint32),
        ]

    max_path = 32768
    file_buffer = ctypes.create_unicode_buffer(max_path)
    ofn = OpenFileName()
    ofn.lStructSize = ctypes.sizeof(OpenFileName)
    ofn.lpstrFilter = "CSV files (*.csv)\0*.csv\0All files (*.*)\0*.*\0"
    ofn.lpstrFile = ctypes.cast(file_buffer, ctypes.c_wchar_p)
    ofn.nMaxFile = max_path
    ofn.lpstrTitle = "Select IEEE 738 input CSV"
    ofn.Flags = 0x00001000 | 0x00000800 | 0x00000004
    ofn.lpstrDefExt = "csv"

    if not ctypes.windll.comdlg32.GetOpenFileNameW(ctypes.byref(ofn)):
        return None

    return Path(file_buffer.value)


def show_message(title: str, message: str, is_error: bool = False) -> None:
    icon = 0x10 if is_error else 0x40
    ctypes.windll.user32.MessageBoxW(None, message, title, icon)


def run_gui() -> int:
    input_csv = select_csv_file()
    if input_csv is None:
        return 0

    try:
        report_path = run_from_csv(input_csv)
    except Exception:
        show_message(
            "IEEE 738 Calculation Failed",
            traceback.format_exc(),
            is_error=True,
        )
        return 1

    output_dir = report_path.parent
    show_message(
        "IEEE 738 Calculation Complete",
        "Calculation finished.\n\n"
        f"Report:\n{report_path}\n\n"
        "Figures:\n"
        f"{output_dir / 'current_temperature_curve.png'}\n"
        f"{output_dir / 'transient_step_curve.png'}\n"
        f"{output_dir / 'time_constant_curve.png'}",
    )
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="GUI/CLI wrapper for IEEE 738 CSV calculations."
    )
    parser.add_argument(
        "--input-csv",
        type=Path,
        help="CSV file to run without opening the file picker.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Optional output directory for the report and figures.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.input_csv:
        report_path = run_from_csv(args.input_csv, args.output_dir)
        print(f"Report: {report_path}")
        print(f"Output directory: {report_path.parent}")
        return 0

    return run_gui()


if __name__ == "__main__":
    raise SystemExit(main())
