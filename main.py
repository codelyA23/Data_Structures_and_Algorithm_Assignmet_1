import argparse
import math
import re
import sys
from pathlib import Path
from typing import Generic, TypeVar


T = TypeVar("T")
Number = int | float


class Stack(Generic[T]):
    def __init__(self) -> None:
        self._items: list[T] = []

    def push(self, item: T) -> None:
        self._items.append(item)

    def pop(self) -> T:
        if self.is_empty():
            raise IndexError("Cannot pop from an empty stack.")
        return self._items.pop()

    def peek(self) -> T:
        if self.is_empty():
            raise IndexError("Cannot peek at an empty stack.")
        return self._items[-1]

    def is_empty(self) -> bool:
        return not self._items

    def __len__(self) -> int:
        return len(self._items)

    def snapshot(self) -> list[T]:
        return self._items.copy()


class ExpressionError(ValueError):
    pass


TOKEN_PATTERN = re.compile(r"[0-9]+(?:\.[0-9]*)?|\.[0-9]+|[()+*/-]")
SEPARATOR_PATTERN = re.compile(r"([-=*_#])\1{2,}")
PRECEDENCE = {"+": 1, "-": 1, "*": 2, "/": 2, "u+": 3, "u-": 3}


def tokenize(expression: str):
    position = 0
    while position < len(expression):
        if expression[position].isspace():
            position += 1
            continue
        match = TOKEN_PATTERN.match(expression, position)
        if match is None:
            raise ExpressionError(
                f"Unexpected character {expression[position]!r} at column {position + 1}."
            )
        yield match.group(), position + 1
        position = match.end()


def apply_operator(values: Stack[Number], operator: str) -> None:
    required_values = 1 if operator in ("u+", "u-") else 2
    if len(values) < required_values:
        raise ExpressionError("An operator is missing an operand.")

    right = values.pop()
    if operator == "u+":
        result = right
    elif operator == "u-":
        result = -right
    else:
        left = values.pop()
        try:
            if operator == "+":
                result = left + right
            elif operator == "-":
                result = left - right
            elif operator == "*":
                result = left * right
            elif operator == "/":
                if right == 0:
                    raise ExpressionError("Division by zero.")
                result = left / right
            else:
                raise ExpressionError(f"Unsupported operator {operator!r}.")
        except OverflowError as error:
            raise ExpressionError("The result is too large.") from error

    if isinstance(result, float) and not math.isfinite(result):
        raise ExpressionError("The result is too large.")
    values.push(result)


def evaluate_expression(expression: str, trace: list[dict] | None = None) -> Number:
    values: Stack[Number] = Stack()
    operators: Stack[str] = Stack()
    expecting_operand = True
    has_tokens = False
    current_token = ""
    current_column = 0

    def record(action: str, message: str, section: str = "evaluate") -> None:
        if trace is not None:
            trace.append({
                "action": action,
                "message": message,
                "token": current_token,
                "column": current_column,
                "values": [format_result(value) for value in values.snapshot()],
                "operators": operators.snapshot(),
                "section": section,
            })

    def reduce_operator() -> None:
        operator = operators.pop()
        if trace is None:
            apply_operator(values, operator)
            return
        before = values.snapshot()
        apply_operator(values, operator)
        result = format_result(values.peek())
        if operator in ("u+", "u-"):
            calculation = f"{operator[1]}({format_result(before[-1])}) = {result}"
        else:
            calculation = f"{format_result(before[-2])} {operator} {format_result(before[-1])} = {result}"
        record("Apply an operator", f"{calculation}. Pop the operand(s), then push the result.", "apply")

    record("Start", "Start with an empty value stack and an empty operator stack.", "stack")

    for token, column in tokenize(expression):
        has_tokens = True
        current_token, current_column = token, column
        if token[0] in "0123456789.":
            if not expecting_operand:
                raise ExpressionError(f"Missing operator at column {column}.")
            try:
                number = float(token) if "." in token else int(token)
            except ValueError as error:
                raise ExpressionError(f"Invalid number at column {column}.") from error
            if isinstance(number, float) and not math.isfinite(number):
                raise ExpressionError(f"Number is too large at column {column}.")
            values.push(number)
            expecting_operand = False
            record("Push a number", f"Read {token} and push it onto the value stack.", "stack")
        elif token == "(":
            if not expecting_operand:
                raise ExpressionError(f"Missing operator before '(' at column {column}.")
            operators.push(token)
            record("Open parentheses", "Push '(' onto the operator stack. It marks the start of a group.")
        elif token == ")":
            if expecting_operand:
                raise ExpressionError(f"Missing operand before ')' at column {column}.")
            while not operators.is_empty() and operators.peek() != "(":
                reduce_operator()
            if operators.is_empty():
                raise ExpressionError(f"Unmatched ')' at column {column}.")
            operators.pop()
            expecting_operand = False
            record("Close parentheses", "The group is evaluated. Pop '(' from the operator stack.")
        elif expecting_operand:
            if token not in ("+", "-"):
                raise ExpressionError(f"Missing operand at column {column}.")
            # Unary signs associate right-to-left, so leave earlier signs on the stack.
            operators.push("u" + token)
            record("Push a unary sign", f"Treat {token} as a sign for the next value or group.")
        else:
            # Apply operators with higher or equal precedence first.
            while (
                not operators.is_empty()
                and operators.peek() != "("
                and PRECEDENCE[operators.peek()] >= PRECEDENCE[token]
            ):
                reduce_operator()
            operators.push(token)
            expecting_operand = True
            record("Push an operator", f"Push '{token}' after applying any earlier operator with equal or higher precedence.")

    if not has_tokens:
        raise ExpressionError("The expression is empty.")
    if expecting_operand:
        raise ExpressionError("The expression ends without an operand.")

    while not operators.is_empty():
        if operators.peek() == "(":
            raise ExpressionError("Unmatched '('.")
        reduce_operator()

    if len(values) != 1:
        raise ExpressionError("Invalid expression.")
    record("Complete", f"The operator stack is empty. The remaining value, {format_result(values.peek())}, is the result.")
    return values.pop()


def format_result(value: Number) -> str:
    if isinstance(value, int):
        return str(value)
    if value.is_integer():
        return str(int(value))
    return format(value, ".15g")


def read_expressions(input_file: Path) -> list[str]:
    # Disable newline conversion to preserve the input file's line endings.
    with input_file.open("r", encoding="utf-8-sig", newline="") as source:
        return source.readlines()


def process_file(input_file: Path, output_file: Path) -> tuple[int, list[str]]:
    if input_file.resolve() == output_file.resolve() or (
        output_file.exists() and input_file.samefile(output_file)
    ):
        raise ValueError("Input and output must be different files.")

    lines = read_expressions(input_file)
    output_lines: list[str] = []
    errors: list[str] = []
    expression_count = 0

    for line_number, line in enumerate(lines, start=1):
        body = line.rstrip("\r\n")
        ending = line[len(body):]
        if not body.strip() or SEPARATOR_PATTERN.fullmatch(body.strip()):
            output_lines.append(line)
            continue

        expression_count += 1
        try:
            result = format_result(evaluate_expression(body))
        except (ExpressionError, ValueError) as error:
            result = f"Error: {error}"
            errors.append(f"Line {line_number}: {error}")

        leading_space = body[:len(body) - len(body.lstrip(" \t"))]
        trailing_space = body[len(body.rstrip(" \t")):]
        output_lines.append(f"{leading_space}{result}{trailing_space}{ending}")

    with output_file.open("w", encoding="utf-8", newline="") as destination:
        destination.writelines(output_lines)
    return expression_count, errors


def main(argv: list[str] | None = None) -> int:
    app_directory = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description="Evaluate input.txt using stacks and write results to output.txt."
    )
    parser.add_argument(
        "input_file", nargs="?", type=Path, default=app_directory / "input.txt"
    )
    parser.add_argument(
        "output_file", nargs="?", type=Path, default=app_directory / "output.txt"
    )
    args = parser.parse_args(argv)

    try:
        count, errors = process_file(args.input_file, args.output_file)
    except (OSError, UnicodeError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    print(f"Processed {count} expression(s). Results written to {args.output_file}.")
    for error in errors:
        print(error, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
