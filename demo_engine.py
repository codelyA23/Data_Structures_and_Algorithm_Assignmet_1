import json
import tempfile
from pathlib import Path

from main import ExpressionError, SEPARATOR_PATTERN, evaluate_expression, format_result, process_file, tokenize


def evaluate_demo(expression):
    trace = []
    tokens = []
    try:
        tokens = [{"text": text, "column": column} for text, column in tokenize(expression)]
        result = format_result(evaluate_expression(expression, trace))
        return {"ok": True, "result": result, "steps": trace, "tokens": tokens}
    except (ExpressionError, ValueError) as error:
        return {"ok": False, "error": str(error), "steps": trace, "tokens": tokens}


def batch_demo(text):
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "input.txt"
        destination = Path(directory) / "output.txt"
        source.write_text(text, encoding="utf-8", newline="")
        count, errors = process_file(source, destination)
        with source.open(encoding="utf-8-sig", newline="") as file:
            inputs = file.readlines()
        with destination.open(encoding="utf-8", newline="") as file:
            outputs = file.readlines()
        rows = []
        for line, (expression, result) in enumerate(zip(inputs, outputs), start=1):
            body = expression.rstrip("\r\n")
            if not body.strip() or SEPARATOR_PATTERN.fullmatch(body.strip()):
                continue
            rows.append({"line": line, "expression": body.strip(), "result": result.strip(), "ok": not result.strip().startswith("Error:")})
        return {"output": "".join(outputs), "count": count, "errors": errors, "rows": rows}
