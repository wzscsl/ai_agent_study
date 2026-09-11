"""简单计算器 demo：支持加减乘除、取模、幂运算。"""


def add(a: float, b: float) -> float:
    return a + b


def subtract(a: float, b: float) -> float:
    return a - b


def multiply(a: float, b: float) -> float:
    return a * b


def divide(a: float, b: float) -> float:
    if b == 0:
        raise ZeroDivisionError("除数不能为零")
    return a / b


def modulo(a: float, b: float) -> float:
    if b == 0:
        raise ZeroDivisionError("除数不能为零")
    return a % b


def power(a: float, b: float) -> float:
    return a ** b


OPERATIONS = {
    "+": add,
    "-": subtract,
    "*": multiply,
    "/": divide,
    "%": modulo,
    "**": power,
}


def calculate(a: float, op: str, b: float) -> float:
    if op not in OPERATIONS:
        raise ValueError(f"不支持的运算符: {op}，支持: {', '.join(OPERATIONS)}")
    return OPERATIONS[op](a, b)


if __name__ == "__main__":
    print("=== 计算器 demo ===")
    print("支持运算符: +  -  *  /  %  **，输入 q 退出")
    while True:
        try:
            expr = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break
        if expr.lower() in ("q", "quit", "exit"):
            print("再见！")
            break
        parts = expr.split()
        if len(parts) != 3:
            print("格式错误，示例: 3 + 4")
            continue
        try:
            a, op, b = float(parts[0]), parts[1], float(parts[2])
            print(f"= {calculate(a, op, b)}")
        except ValueError as e:
            print(f"错误: {e}")
        except ZeroDivisionError as e:
            print(f"错误: {e}")
