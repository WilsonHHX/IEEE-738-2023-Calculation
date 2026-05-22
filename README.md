# IEEE-738-2023-Calculation

A Python/Windows tool for overhead conductor ampacity and thermal calculations based on IEEE 738.

The project includes:

- IEEE 738 heat-balance calculation modules
- CSV input templates for user data
- Drake/IEEE example input for result checking
- A Windows single-file executable with a CSV file picker
- TXT report output with intermediate and final numeric results
- Three PNG plots:
  - current-temperature curve
  - transient current-step temperature curve
  - Annex D time-constant approximation

## Quick Use

For most Windows users, run:

```text
dist/IEEE738_Calculator.exe
```

The app will ask you to select a CSV input file. After calculation, it creates a results folder next to the selected CSV file:

```text
<input_csv_name>_results/
```

That folder contains:

```text
calculation_report.txt
current_temperature_curve.png
transient_step_curve.png
time_constant_curve.png
```

## Input Files

Use one of these CSV files as a starting point:

- `examples/general_input.csv`: general user input template
- `examples/example_drake.csv`: Drake/IEEE example values for comparison

The CSV format has four columns:

```text
name,variable_name,value,unit
```

Users should normally edit only the `value` column.

## Run From Python

Create/activate a Python environment, install dependencies, then run:

```powershell
pip install -r requirements.txt
python examples/run_drake.py --input-csv examples/general_input.csv
```

To use the app wrapper without the GUI picker:

```powershell
python ieee738_app.py --input-csv examples/example_drake.csv --output-dir outputs/example_drake_test
```

## Build The EXE

```powershell
pyinstaller --onefile --windowed --clean --name IEEE738_Calculator ieee738_app.py
```

The executable is written to:

```text
dist/IEEE738_Calculator.exe
```

## License

Author: Haixiang Huang

This project is released under the MIT License. See `LICENSE`.
