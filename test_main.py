import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from main import ExpressionError, Stack, evaluate_expression, format_result, main, process_file


class StackTests(unittest.TestCase):
    def test_lifo_and_peek(self):
        stack = Stack()
        self.assertTrue(stack.is_empty())
        stack.push(10)
        stack.push(20)
        self.assertEqual(stack.peek(), 20)
        self.assertEqual(len(stack), 2)
        self.assertEqual(stack.pop(), 20)
        self.assertEqual(stack.pop(), 10)
        self.assertTrue(stack.is_empty())

    def test_empty_stack_operations(self):
        stack = Stack()
        with self.assertRaises(IndexError):
            stack.pop()
        with self.assertRaises(IndexError):
            stack.peek()


class ExpressionTests(unittest.TestCase):
    def test_valid_expressions(self):
        examples = {
            "3 + 5 * 2": 13,
            "(8 / 4) + 7 * 2": 16,
            "10 - (2 + 3) * 4": -10,
            "20 / 5 / 2": 2,
            "10 - 3 - 2": 5,
            "((2 + 3) * (4 - 1)) / 5": 3,
            "-3 + 5": 2,
            "2 * -3": -6,
            "-(2 + 3) * 4": -20,
            "--2 + +3": 5,
            "1 - -2": 3,
            "2 / -(1 + 3)": -0.5,
            "-(-(-2))": -2,
            "2.5 * 4 + .5": 10.5,
            "3.": 3,
            " \t42 ": 42,
            "7 / 2": 3.5,
            "2 * (3 + -(4 - 6))": 10,
        }
        for expression, expected in examples.items():
            with self.subTest(expression=expression):
                self.assertEqual(evaluate_expression(expression), expected)

    def test_invalid_expressions(self):
        examples = [
            "", "   ", "()", "2 +", "* 2", "2 3", "2(3 + 4)",
            "(2)(3)", "(2 + 3", "2 + 3)", "2 + * 3", "1..2",
            "1 / 0", "2 / (3 - 3)", "1 // 2", "2 ** 3", "2 ^ 3",
            "__import__('os')", "(2 + )", "2 + -", "1e3", "NaN",
        ]
        for expression in examples:
            with self.subTest(expression=expression):
                with self.assertRaises(ExpressionError):
                    evaluate_expression(expression)

    def test_decimal_output(self):
        self.assertEqual(format_result(evaluate_expression(".1 + .2")), "0.3")
        self.assertEqual(format_result(evaluate_expression("8 / 4")), "2")
        self.assertEqual(format_result(evaluate_expression("1 / 3")), "0.333333333333333")

    def test_large_integer_and_deep_parentheses(self):
        self.assertEqual(evaluate_expression("12345678901234567890 + 1"), 12345678901234567891)
        self.assertEqual(evaluate_expression("(" * 2000 + "2 + 3" + ")" * 2000), 5)

    def test_trace_records_real_operations(self):
        trace = []
        self.assertEqual(evaluate_expression("3 + 5 * 2", trace), 13)
        self.assertEqual(trace[0]["values"], [])
        self.assertEqual(trace[-1]["values"], ["13"])
        self.assertEqual(trace[-1]["operators"], [])
        applications = [step["message"] for step in trace if step["section"] == "apply"]
        self.assertTrue(applications[0].startswith("5 * 2 = 10"))
        self.assertTrue(applications[1].startswith("3 + 10 = 13"))
        self.assertEqual(trace[1]["values"], ["3"])

    def test_unary_trace(self):
        trace = []
        self.assertEqual(evaluate_expression("-(2 + 3)", trace), -5)
        self.assertEqual(trace[-1]["values"], ["-5"])
        self.assertTrue(any(step["message"].startswith("-(5) = -5") for step in trace))


class FileTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.input_file = Path(self.directory.name) / "input.txt"
        self.output_file = Path(self.directory.name) / "output.txt"

    def test_sample_output(self):
        self.input_file.write_text("3 + 5 * 2\n-----\n(8 / 4) + 7 * 2\n-----\n10 - (2 + 3) * 4\n")
        count, errors = process_file(self.input_file, self.output_file)
        self.assertEqual(count, 3)
        self.assertEqual(errors, [])
        self.assertEqual(self.output_file.read_text(), "13\n-----\n16\n-----\n-10\n")

    def test_exact_file_format_preservation(self):
        self.input_file.write_bytes(b"  3 + 5 * 2 \r\n ----- \r\n\r\n7/2\r\n=====\n\t-2\t")
        process_file(self.input_file, self.output_file)
        self.assertEqual(self.output_file.read_bytes(), b"  13 \r\n ----- \r\n\r\n3.5\r\n=====\n\t-2\t")

    def test_invalid_line_does_not_stop_later_expressions(self):
        self.input_file.write_text("1/0\n-----\n2+3\n")
        count, errors = process_file(self.input_file, self.output_file)
        self.assertEqual(count, 2)
        self.assertEqual(errors, ["Line 1: Division by zero."])
        self.assertEqual(self.output_file.read_text(), "Error: Division by zero.\n-----\n5\n")

    def test_empty_file(self):
        self.input_file.write_text("")
        self.assertEqual(process_file(self.input_file, self.output_file), (0, []))
        self.assertEqual(self.output_file.read_bytes(), b"")

    def test_utf8_bom(self):
        self.input_file.write_bytes(b"\xef\xbb\xbf1+2\n")
        process_file(self.input_file, self.output_file)
        self.assertEqual(self.output_file.read_text(), "3\n")

    def test_cannot_overwrite_input(self):
        self.input_file.write_text("2+3\n")
        with self.assertRaises(ValueError):
            process_file(self.input_file, self.input_file)
        self.assertEqual(self.input_file.read_text(), "2+3\n")

    def test_hard_link_cannot_overwrite_input(self):
        self.input_file.write_text("2+3\n")
        self.output_file.hardlink_to(self.input_file)
        with self.assertRaises(ValueError):
            process_file(self.input_file, self.output_file)
        self.assertEqual(self.input_file.read_text(), "2+3\n")

    def test_cli_success_and_errors(self):
        arguments = [str(self.input_file), str(self.output_file)]
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(arguments), 1)
            self.input_file.write_text("2+3\n")
            self.assertEqual(main(arguments), 0)
            self.input_file.write_text("2+\n")
            self.assertEqual(main(arguments), 1)


if __name__ == "__main__":
    unittest.main()
