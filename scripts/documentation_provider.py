# Copyright (c) Microsoft Corporation.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import re
import subprocess
from sys import stderr
from typing import (  # type: ignore
    Any,
    Dict,
    List,
    Set,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)

from playwright._impl._helper import to_snake_case

enum_regex = r"^\"[^\"]+\"(?:\|\"[^\"]+\")+$"
union_regex = r"^[^\|]+(?:\|[^\|]+)+$"

exceptions = {
    "Route.fulfill(path=)": {
        "doc": "Optional[str]",
        "code": "Union[str, pathlib.Path, NoneType]",
    },
    "Browser.newContext(viewport=)": {
        "doc": 'Optional[{"width": int, "height": int}]',
        "code": 'Union[{"width": int, "height": int}, \'0\', NoneType]',
    },
    "Browser.newPage(viewport=)": {
        "doc": 'Optional[{"width": int, "height": int}]',
        "code": 'Union[{"width": int, "height": int}, \'0\', NoneType]',
    },
}


class DocumentationProvider:
    def __init__(self) -> None:
        self.api: Any = {}
        self.printed_entries: List[str] = []
        process_output = subprocess.run(
            ["python", "-m", "playwright", "print-api-json"],
            check=True,
            capture_output=True,
        )
        self.api = json.loads(process_output.stdout)
        self.errors: Set[str] = set()
        self._patch_descriptions()

    method_name_rewrites: Dict[str, str] = {
        "continue_": "continue",
        "evalOnSelector": "$eval",
        "evalOnSelectorAll": "$$eval",
        "querySelector": "$",
        "querySelectorAll": "$$",
    }

    def _patch_descriptions(self) -> None:
        map: Dict[str, str] = {}
        for class_name in self.api:
            clazz = self.api[class_name]
            js_class = ""
            if class_name.startswith("JS"):
                js_class = "jsHandle"
            if class_name.startswith("CDP"):
                js_class = "cdpSession"
            else:
                js_class = class_name[0:1].lower() + class_name[1:]
            for method_name in clazz["methods"]:
                camel_case = js_class + "." + method_name
                snake_case = (
                    to_snake_case(class_name) + "." + to_snake_case(method_name)
                )
                map[camel_case] = snake_case

        for [name, value] in map.items():
            for class_name in self.api:
                clazz = self.api[class_name]
                for method_name in clazz["methods"]:
                    method = clazz["methods"][method_name]
                    if "comment" in method:
                        method["comment"] = method["comment"].replace(name, value)
                    if "args" in method:
                        for _, arg in method["args"].items():
                            if "comment" in arg:
                                arg["comment"] = arg["comment"].replace(name, value)

    def print_entry(
        self, class_name: str, method_name: str, signature: Dict[str, Any] = None
    ) -> None:
        if class_name in ["BindingCall", "Playwright"] or method_name in [
            "pid",
            "_add_event_handler",
            "remove_listener",
        ]:
            return
        original_method_name = method_name
        if method_name in self.method_name_rewrites:
            method_name = self.method_name_rewrites[method_name]
        self.printed_entries.append(f"{class_name}.{method_name}")
        if class_name == "JSHandle":
            self.printed_entries.append(f"ElementHandle.{method_name}")
        clazz = self.api[class_name]
        super_clazz = self.api.get(clazz.get("extends"))
        method = (
            clazz["methods"].get(method_name)
            or clazz["properties"].get(method_name)
            or (super_clazz and super_clazz["methods"].get(method_name))
        )
        fqname = f"{class_name}.{method_name}"

        if not method:
            self.errors.add(f"Method not documented: {fqname}")
            return

        indent = " " * 8
        print(f'{indent}"""{class_name}.{to_snake_case(original_method_name)}')
        if method.get("comment"):
            print(f"{indent}{self.beautify_method_comment(method['comment'], indent)}")
        signature_no_return = {**signature} if signature else None
        if signature_no_return and "return" in signature_no_return:
            del signature_no_return["return"]

        # Collect a list of all names, flatten options.
        args = method["args"]
        args_with_expanded_options: Dict[str, Any] = dict()
        for name, value in args.items():
            expand = False
            if name == "options":
                expand = True
            if fqname == "Page.frame" and name == "frameSelector":
                expand = True
            if ".addStyleTag" in fqname and name == "style":
                expand = True
            if ".addScriptTag" in fqname and name == "script":
                expand = True
            if fqname == "Page.emulateMedia" and name == "params":
                expand = True
            if fqname == "Route.fulfill" and name == "response":
                expand = True
            if fqname == "Route.continue" and name == "overrides":
                expand = True
            if fqname == "Page.setViewportSize" and name == "viewportSize":
                expand = True
            if fqname == "BrowserContext.setGeolocation" and name == "geolocation":
                expand = True
            if expand:
                for opt_name, opt_value in args[name]["type"]["properties"].items():
                    if opt_name == "recordHar" or opt_name == "recordVideo":
                        for sub_name, sub_value in opt_value["type"][
                            "properties"
                        ].items():
                            args_with_expanded_options[
                                opt_name + sub_name[0:1].upper() + sub_name[1:]
                            ] = sub_value
                    else:
                        args_with_expanded_options[opt_name] = opt_value
            else:
                args_with_expanded_options[name] = value

        if signature and signature_no_return:
            print("")
            print("        Parameters")
            print("        ----------")
            for [name, value] in signature.items():
                if name == "return":
                    continue
                if name == "force_expr":
                    continue
                original_name = name
                name = self.rewrite_param_name(fqname, method_name, name)
                doc_value = args_with_expanded_options.get(name)
                if name in args_with_expanded_options:
                    del args_with_expanded_options[name]
                if not doc_value:
                    self.errors.add(f"Parameter not documented: {fqname}({name}=)")
                else:
                    code_type = self.serialize_python_type(value)

                    print(f"{indent}{to_snake_case(original_name)} : {code_type}")
                    if doc_value.get("comment"):
                        print(
                            f"{indent}    {self.indent_paragraph(doc_value['comment'], f'{indent}    ')}"
                        )
                    if original_name == "expression":
                        print(f"{indent}force_expr : bool")
                        print(
                            f"{indent}    Whether to treat given expression as JavaScript evaluate expression, even though it looks like an arrow function"
                        )
                    self.compare_types(code_type, doc_value, f"{fqname}({name}=)")
        if (
            signature
            and "return" in signature
            and str(signature["return"]) != "<class 'NoneType'>"
        ):
            value = signature["return"]
            doc_value = method
            self.compare_types(value, doc_value, f"{fqname}(return=)")
            print("")
            print("        Returns")
            print("        -------")
            print(f"        {self.serialize_python_type(value)}")
            if method.get("returnComment"):
                print(
                    f"            {self.indent_paragraph(method['returnComment'], '              ')}"
                )
        print(f'{indent}"""')

        for name in args_with_expanded_options:
            self.errors.add(
                f"Parameter not implemented: {class_name}.{method_name}({name}=)"
            )

    def indent_paragraph(self, p: str, indent: str) -> str:
        lines = p.split("\n")
        result = [lines[0]]
        for line in lines[1:]:
            result.append(indent + line)
        return "\n".join(result)

    def beautify_method_comment(self, comment: str, indent: str) -> str:
        lines = comment.split("\n")
        result = []
        in_example = False
        last_was_blank = True
        for line in lines:
            if not line.strip():
                last_was_blank = True
                continue
            if line.strip() == "```js":
                in_example = True
            if not in_example:
                if last_was_blank:
                    last_was_blank = False
                    result.append("")
                result.append(line)
            if line.strip() == "```":
                in_example = False
        return self.indent_paragraph("\n".join(result), indent)

    def make_optional(self, text: str) -> str:
        if text.startswith("Union["):
            return text[:-1] + ", NoneType]"
        if text.startswith("Optional["):
            return text
        return f"Optional[{text}]"

    def compare_types(self, value: Any, doc_value: Any, fqname: str) -> None:
        if "(arg=)" in fqname or "(pageFunction=)" in fqname:
            return
        code_type = self.serialize_python_type(value)
        doc_type = self.serialize_doc_type(
            doc_value["type"]["name"],
            fqname,
            doc_value["type"],
        )
        if not doc_value["required"]:
            doc_type = self.make_optional(doc_type)
        if (
            fqname in exceptions
            and exceptions[fqname]["doc"] == doc_type
            and exceptions[fqname]["code"] == code_type
        ):
            return

        if doc_type != code_type:
            self.errors.add(
                f"Parameter type mismatch in {fqname}: documented as {doc_type}, code has {code_type}"
            )

    def serialize_python_type(self, value: Any) -> str:
        str_value = str(value)
        if isinstance(value, list):
            return f"[{', '.join(list(map(lambda a: self.serialize_python_type(a), value)))}]"
        if str_value == "<class 'playwright._impl._types.Error'>":
            return "Error"
        match = re.match(r"^<class '((?:pathlib\.)?\w+)'>$", str_value)
        if match:
            return match.group(1)
        match = re.match(r"^<class 'playwright\._impl\.[\w_]+\.([\w]+)'>$", str_value)
        if match and "_api_structures" not in str_value:
            if match.group(1) == "FilePayload":
                return "Dict"
            if match.group(1) == "FloatRect":
                return '{"x": float, "y": float, "width": float, "height": float}'
            if match.group(1) == "Geolocation":
                return '{"latitude": float, "longitude": float, "accuracy": Optional[float]}'
            if match.group(1) == "PdfMargins":
                return '{"top": Union[str, int, NoneType], "right": Union[str, int, NoneType], "bottom": Union[str, int, NoneType], "left": Union[str, int, NoneType]}'
            if match.group(1) == "ProxySettings":
                return '{"server": str, "bypass": Optional[str], "username": Optional[str], "password": Optional[str]}'
            if match.group(1) == "SourceLocation":
                return '{"url": str, "lineNumber": int, "columnNumber": int}'

            return match.group(1)

        match = re.match(r"^typing\.(\w+)$", str_value)
        if match:
            return match.group(1)

        origin = get_origin(value)
        args = get_args(value)
        hints = None
        try:
            hints = get_type_hints(value)
        except Exception:
            pass
        if hints:
            signature: List[str] = []
            for [name, value] in hints.items():
                signature.append(f'"{name}": {self.serialize_python_type(value)}')
            return f"{{{', '.join(signature)}}}"
        if origin == Union:
            args = get_args(value)
            if len(args) == 2 and "None" in str(args[1]):
                return self.make_optional(self.serialize_python_type(args[0]))
            return f"Union[{', '.join(list(map(lambda a: self.serialize_python_type(a), args)))}]"
        if str(origin) == "<class 'dict'>":
            args = get_args(value)
            return f"Dict[{', '.join(list(map(lambda a: self.serialize_python_type(a), args)))}]"
        if str(origin) == "<class 'list'>":
            args = get_args(value)
            return f"List[{', '.join(list(map(lambda a: self.serialize_python_type(a), args)))}]"
        if str(origin) == "<class 'collections.abc.Callable'>":
            args = get_args(value)
            return f"Callable[{', '.join(list(map(lambda a: self.serialize_python_type(a), args)))}]"
        if str(origin) == "typing.Literal":
            args = get_args(value)
            if len(args) == 1:
                return "'" + self.serialize_python_type(args[0]) + "'"
            body = ", ".join(
                list(map(lambda a: "'" + self.serialize_python_type(a) + "'", args))
            )
            return f"Literal[{body}]"
        return str_value

    def serialize_doc_type(
        self, type_name: Any, fqname: str, doc_type: Any = None
    ) -> str:
        type_name = re.sub(r"^Promise<(.*)>$", r"\1", type_name)

        if type_name == "string":
            return "str"

        if type_name == "Buffer":
            return "bytes"

        if type_name == "Array":
            return "List"

        if type_name == "boolean":
            return "bool"

        if type_name == "number":
            if fqname == "Request.timing(return=)" or "ResourceTiming" in fqname:
                return "float"
            if ("Mouse" in fqname or "Touchscreen" in fqname) and (
                "(x=)" in fqname or "(y=)" in fqname
            ):
                return "float"
            if (
                "(position=)" in fqname
                or "(geolocation=)" in fqname
                or ".boundingBox(" in fqname
            ):
                return "float"
            if "screenshot(clip=)" in fqname:
                return "float"
            if fqname == "Page.pdf(width=)" or fqname == "Page.pdf(height=)":
                return "float"
            if fqname.startswith("BrowserContext.setGeolocation"):
                return "float"
            return "int"

        if type_name == "Serializable":
            return "Any"

        if type_name == "Object" or type_name == "?Object":
            intermediate = "Dict"
            if doc_type and "properties" in doc_type and len(doc_type["properties"]):
                signature: List[str] = []
                for [name, value] in doc_type["properties"].items():
                    value_type = self.serialize_doc_type(
                        value["type"]["name"], fqname, value["type"]
                    )
                    signature.append(
                        f"\"{name}\": {value_type if value['required'] else self.make_optional(value_type)}"
                    )
                intermediate = f"{{{', '.join(signature)}}}"
            return (
                intermediate
                if type_name == "Object"
                else self.make_optional(intermediate)
            )

        if type_name == "function":
            return "Callable"

        match = re.match(r"^Object<([^,]+),\s*([^)]+)>$", type_name)
        if match:
            return f"Dict[{self.serialize_doc_type(match.group(1), fqname)}, {self.serialize_doc_type(match.group(2), fqname)}]"

        match = re.match(r"^Map<([^,]+),\s*([^)]+)>$", type_name)
        if match:
            return f"Dict[{self.serialize_doc_type(match.group(1), fqname)}, {self.serialize_doc_type(match.group(2), fqname)}]"

        if re.match(enum_regex, type_name):
            result = f"Literal[{', '.join(type_name.split('|'))}]"
            return result.replace('"', "'")

        match = re.match(r"^Array<(.*)>$", type_name)
        if match:
            return f"List[{self.serialize_doc_type(match.group(1), fqname)}]"

        match = re.match(r"^\?(.*)$", type_name)
        if match:
            return self.make_optional(self.serialize_doc_type(match.group(1), fqname))

        match = re.match(r"^null\|(.*)$", type_name)
        if match:
            return self.make_optional(self.serialize_doc_type(match.group(1), fqname))

        # Union detection is greedy
        if re.match(union_regex, type_name):
            result = ", ".join(
                list(
                    map(
                        lambda a: self.serialize_doc_type(a, fqname),
                        type_name.split("|"),
                    )
                )
            )
            body = result.replace('"', "'")
            return f"Union[{body}]"

        return type_name

    def rewrite_param_name(self, fqname: str, method_name: str, name: str) -> str:
        if name == "expression":
            return "pageFunction"
        if method_name == "exposeBinding" and name == "binding":
            return "playwrightBinding"
        if method_name == "exposeFunction" and name == "binding":
            return "playwrightFunction"
        if method_name == "addInitScript" and name == "source":
            return "script"
        if fqname == "Selectors.register" and name == "source":
            return "script"
        if fqname == "Page.waitForRequest" and name == "url":
            return "urlOrPredicate"
        if fqname == "Page.waitForResponse" and name == "url":
            return "urlOrPredicate"
        return name

    def print_remainder(self) -> None:
        for [class_name, value] in self.api.items():
            class_name = re.sub(r"Chromium(.*)", r"\1", class_name)
            class_name = re.sub(r"WebKit(.*)", r"\1", class_name)
            class_name = re.sub(r"Firefox(.*)", r"\1", class_name)
            for [method_name, method] in list(value["methods"].items()) + list(
                value["properties"].items()
            ):
                entry = f"{class_name}.{method_name}"
                if entry not in self.printed_entries:
                    self.errors.add(f"Method not implemented: {entry}")

        with open("scripts/expected_api_mismatch.txt") as f:
            for line in f.readlines():
                sline = line.strip()
                if not len(sline) or sline.startswith("#"):
                    continue
                if sline in self.errors:
                    self.errors.remove(sline)
                else:
                    print("No longer there: " + sline, file=stderr)

        if len(self.errors) > 0:
            for error in self.errors:
                print(error, file=stderr)
            exit(1)


if __name__ == "__main__":
    DocumentationProvider().print_entry("Page", "goto")
    DocumentationProvider().print_entry("Page", "evaluateHandle")
    DocumentationProvider().print_entry("ElementHandle", "click")
    DocumentationProvider().print_entry("Page", "screenshot")
