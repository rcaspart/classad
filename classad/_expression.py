import operator
import pyparsing as pp
from typing import Any

from classad._primitives import Undefined, Error
from . import _functions
from ._classad import ClassAd


def scope_up(key: str):
    return ".".join(key.split(".")[:-1])


def evaluate_isnt_operator(a, b):
    return a.__isnt__(b)


def evaluate_is_operator(a, b):
    return a.__is__(b)


class Expression:
    def __init__(self):
        self._expression = None

    def evaluate(
        self, key: str = None, my: ClassAd = None, target: ClassAd = None
    ) -> Any:
        return NotImplemented

    @classmethod
    def from_grammar(cls, tokens):
        if isinstance(tokens, pp.ParseResults):
            if len(tokens) == 1:
                return tokens[0]
        result = cls()
        result._expression = tokens
        return result

    def __repr__(self):
        return f"<{self.__class__.__name__}>: {self._expression}"

    def __eq__(self, other):
        return type(self) == type(other) and self._expression == other._expression


class NamedExpression(Expression):
    @classmethod
    def from_grammar(cls, tokens):
        result = cls()
        result._expression = tokens
        return result


class FunctionExpression(Expression):
    def __init__(self, name, args):
        super().__init__()
        self._name = name
        self._expression = args

    def __eq__(self, other):
        return (
            type(self) == type(other)
            and self._expression == other._expression
            and self._name == other._name
        )

    def evaluate(
        self, key: str = None, my: ClassAd = None, target: ClassAd = None
    ) -> Any:
        expression = []
        for element in self._expression:
            if isinstance(element, Expression):
                expression.append(element.evaluate(my, target))
            else:
                expression.append(element)
        return getattr(_functions, self._name)(*expression)

    @classmethod
    def from_grammar(cls, tokens):
        return cls(tokens[0], tokens[1])

    def __repr__(self):
        return f"<{self.__class__.__name__}>: {self._name}{self._expression}"


class TernaryExpression(Expression):
    @classmethod
    def from_grammar(cls, tokens):
        if tokens[0]:
            return tokens[1]
        else:
            return tokens[2]


class DotExpression(Expression):
    def evaluate(
        self, key: str = None, my: ClassAd = None, target: ClassAd = None
    ) -> Any:
        checked = set()
        to_check = self._expression[1]
        while isinstance(to_check, AttributeExpression):
            if to_check._expression not in checked:
                checked.add(to_check._expression)
                to_check = self._expression[0][to_check._expression]
            else:
                return Undefined()
        return to_check


class SubscriptableExpression(Expression):
    @classmethod
    def from_grammar(cls, tokens):
        if len(tokens) == 2:
            return tokens[0][tokens[1]]
        return NotImplemented


class AttributeExpression(Expression):
    def __add__(self, other):
        raise ArithmeticError

    def __sub__(self, other):
        raise ArithmeticError

    def __mul__(self, other):
        raise ArithmeticError

    def __truediv__(self, other):
        raise ArithmeticError

    def __lt__(self, other):
        raise TypeError

    def __le__(self, other):
        raise TypeError

    def __ge__(self, other):
        raise TypeError

    def __gt__(self, other):
        raise TypeError

    def __eq__(self, other):
        if type(self) == type(other):
            if self._expression == other._expression:
                return True
            return False
        raise TypeError

    def __ne__(self, other):
        raise TypeError

    def __and__(self, other):
        raise ArithmeticError

    def __or__(self, other):
        raise ArithmeticError

    def __isnt__(self, other):
        raise TypeError

    def __is__(self, other):
        raise TypeError

    def evaluate(
        self, key: str = None, my: ClassAd = None, target: ClassAd = None
    ) -> Any:
        def find_scope(current_key):
            if len(current_key) > 0:
                return my[current_key]
            return my

        value = Undefined()
        if self._expression[0] == ".":
            key = scope_up(self._expression[1])
            expression = self._expression[1].split(".")[-1]
        elif self._expression[0] == "super":
            key = scope_up(key)
            expression = self._expression[1]
        else:
            expression = self._expression
        try:
            context = find_scope(key)
        except TypeError:
            return Error()
        while isinstance(value, Undefined):
            value = context[expression]
            if isinstance(value, Undefined):
                if len(key) == 0:
                    return Undefined()
                key = scope_up(key)
                context = find_scope(key)
        if isinstance(value, AttributeExpression):
            return value.evaluate(key=key, my=my, target=target)
        return value

    @classmethod
    def from_grammar(cls, tokens):
        result = cls()
        if isinstance(tokens, pp.ParseResults):
            if isinstance(tokens[0], ClassAd):
                result = DotExpression()
                result._expression = tokens
            elif isinstance(tokens[0], str) and tokens[0] == ".":
                result._expression = ["."]
                tokens = tokens[1:]
                result._expression.append(
                    ".".join([token._expression for token in tokens])
                )
            elif isinstance(tokens[0], NamedExpression):
                result._expression = [tokens[0]._expression]
                tokens = tokens[1:]
                result._expression.append(
                    ".".join([token._expression for token in tokens])
                )
            else:
                result._expression = ".".join([token._expression for token in tokens])
        else:
            result._expression = tokens
        return result


class ArithmeticExpression(Expression):
    operator_map = {
        "+": operator.add,
        "-": operator.sub,
        "*": operator.mul,
        "/": operator.truediv,
        "<": operator.lt,
        "<=": operator.le,
        "=>": operator.ge,
        ">": operator.gt,
        "==": operator.eq,
        "!=": operator.ne,
        "&&": operator.and_,
        "||": operator.or_,
        "=!=": evaluate_isnt_operator,
        "isnt": evaluate_isnt_operator,
        "=?=": evaluate_is_operator,
        "is": evaluate_is_operator,
    }

    @classmethod
    def from_grammar(cls, tokens):
        result = cls()
        try:
            return result._calculate(tokens[0], tokens[-1], tokens[1])
        except NotImplementedError:
            # TODO: lazy loading required
            if len(tokens) > 1:
                result._expression = tuple(tokens)
            else:
                result._expression = tokens[0]
        return result

    def _calculate(self, first, second, operand):
        try:
            return self.operator_map[operand](first, second)
        except (ArithmeticError, AttributeError, TypeError):
            raise NotImplementedError

    def __eq__(self, other):
        if type(self) == type(other):
            # check operators
            return all(
                (
                    self._expression[0] == other._expression[0],
                    self.operator_map[self._expression[1]]
                    == self.operator_map[other._expression[1]],
                    self._expression[2] == other._expression[2],
                )
            )
        return False

    def evaluate(
        self, key: str = None, my: ClassAd = None, target: ClassAd = None
    ) -> Any:
        result = self._expression[0].evaluate(key=key, my=my, target=target)
        for position in range(0, len(self._expression) - 1, 2):
            second = self._expression[position + 2].evaluate(
                key=key, my=my, target=target
            )
            result = self._calculate(result, second, self._expression[position + 1])
        return result
