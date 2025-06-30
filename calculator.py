"""Simple calculator CLI tool."""

import argparse


def add(a, b):
    return a + b


def subtract(a, b):
    return a - b


def multiply(a, b):
    return a * b


def divide(a, b):
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b


OPERATIONS = {
    'add': add,
    'subtract': subtract,
    'multiply': multiply,
    'divide': divide,
}


def main():
    parser = argparse.ArgumentParser(description="Perform basic arithmetic operations.")
    parser.add_argument('operation', choices=OPERATIONS.keys(), help="Operation to perform")
    parser.add_argument('a', type=float, help="First operand")
    parser.add_argument('b', type=float, help="Second operand")

    args = parser.parse_args()
    result = OPERATIONS[args.operation](args.a, args.b)
    print(result)


if __name__ == '__main__':
    main()
