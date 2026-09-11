def greet_user(name: str | None) -> str:
    if not name or not name.strip():
        return "Hello, friend! It's nice to meet you!"
    return f"Hello, {name.strip()}!"


def calculate_discount(price: float, is_vip: bool) -> float:
    # 这个函数主要用来提供另一个“可搜索但不一定要修改”的示例。
    discount = 0.10 if is_vip else 0.02
    return price * (1 - discount)
