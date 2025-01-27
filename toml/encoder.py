import collections.abc
import datetime
import enum
import ipaddress
import pathlib
import re
from decimal import Decimal
from typing import IO, Any, Union, Optional, NoReturn

from toml.decoder import InlineTableDict


def dump(obj: dict[str, Any],
         out: Union[bytes, str, IO, pathlib.PurePath],
         encoder: Optional["TomlEncoder"] = None) -> NoReturn:
    """Writes out dict as TOML to a file.

    Args:
        obj: Object to dump into TOML.
        out: Path or file object where the TOML should be stored.
        encoder: The ``TomlEncoder`` to use for constructing the output string.

    Returns:
        None.

    Raises:
        TypeError: When something unsupported was passed.
    """

    if isinstance(out, bytes):
        out = out.decode("utf-8")

    if isinstance(out, str):
        out = pathlib.Path(out)

    if isinstance(out, pathlib.PurePath):
        out.write_text(dumps(obj, encoder=encoder), encoding="utf-8")
        return

    if not hasattr(out, "write"):
        raise TypeError("'out' must be string, pathlib object or opened file")

    out.write(dumps(obj, encoder=encoder))


def dumps(obj: dict[str, Any], encoder: Optional["TomlEncoder"] = None):
    """Stringifies input dict as TOML.

    Args:
        obj: Object to dump into TOML.
        encoder: The ``TomlEncoder`` to use for constructing the output string.

    Returns:
        String containing the TOML corresponding to dict.

    Examples:
        ```python
        >>> import toml
        >>> output = {
        ... 'a': "I'm a string",
        ... 'b': ["I'm", "a", "list"],
        ... 'c': 2400
        ... }
        >>> toml.dumps(output)
        'a = "I\'m a string"\nb = [ "I\'m", "a", "list",]\nc = 2400\n'
        ```
    """

    retval = ""
    if encoder is None:
        encoder = TomlEncoder(obj.__class__)
    addtoretval, sections = encoder.dump_sections(obj, "")
    retval += addtoretval
    outer_objs = [id(obj)]
    while sections:
        section_ids = [id(section) for section in sections.values()]
        for outer_obj in outer_objs:
            if outer_obj in section_ids:
                raise ValueError("Circular reference detected")
        outer_objs += section_ids
        newsections = encoder.get_empty_table()
        for section in sections:
            addtoretval, addtosections = encoder.dump_sections(
                sections[section], section)

            if addtoretval or (not addtoretval and not addtosections):
                if retval and retval[-2:] != "\n\n":
                    retval += "\n"
                retval += "[" + section + "]\n"
                if addtoretval:
                    retval += addtoretval
            for s in addtosections:
                newsections[section + "." + s] = addtosections[s]
        sections = newsections
    return retval


def _dump_str(v):
    v = "%r" % v
    singlequote = v.startswith("'")
    if singlequote or v.startswith('"'):
        v = v[1:-1]
    if singlequote:
        v = v.replace("\\'", "'")
        v = v.replace('"', '\\"')
    v = v.split("\\x")
    while len(v) > 1:
        i = -1
        if not v[0]:
            v = v[1:]
        v[0] = v[0].replace("\\\\", "\\")
        # No, I don't know why != works and == breaks
        joinx = v[0][i] != "\\"
        while v[0][:i] and v[0][i] == "\\":
            joinx = not joinx
            i -= 1
        if joinx:
            joiner = "x"
        else:
            joiner = "u00"
        v = [v[0] + joiner + v[1]] + v[2:]
    return str('"' + v[0] + '"')


def _dump_float(v):
    return "{}".format(v).replace("e+0", "e+").replace("e-0", "e-")


def _dump_time(v):
    utcoffset = v.utcoffset()
    if utcoffset is None:
        return v.isoformat()
    # The TOML norm specifies that it's local time thus we drop the offset
    return v.isoformat()[:-6]


class TomlEncoder:
    """Extendable base TOML encoder."""

    def __init__(self, _dict=dict, preserve=False):
        self._dict = _dict
        self.preserve = preserve
        self.dump_by_type = {
            str: _dump_str,
            list: self.dump_list,
            bool: lambda v: str(v).lower(),
            int: lambda v: v,
            float: _dump_float,
            Decimal: _dump_float,
            datetime.datetime: lambda v: v.isoformat().replace('+00:00', 'Z'),
            datetime.time: _dump_time,
            datetime.date: lambda v: v.isoformat(),
        }
        self.dump_by_instance = {
            pathlib.PurePath: lambda v: _dump_str(str(v)),
            # TODO: can enum contain types other than int and str?
            enum.Enum: lambda v: _dump_str(str(v.value)),
            # TODO: add other ipaddress types support
            ipaddress.IPv4Address: lambda v: _dump_str(str(v)),
            collections.abc.Iterable: self.dump_by_type[list],
        }

    def get_dump_function(self, value):
        """Return dump function by value's type.

        Function dispatching:
        * try to get dump function by type(value)
        * if no function matched, try to get it by isinstance(value T)
        * if no function matched, use str dump function
        """

        dump_fn = self.dump_by_type.get(type(value))
        for vtype, func in self.dump_by_instance.items():
            if dump_fn is not None:
                break

            if isinstance(value, vtype):
                dump_fn = func

        if dump_fn is None:
            dump_fn = self.dump_by_type[str]

        return dump_fn

    def get_empty_table(self):
        return self._dict()

    def dump_list(self, v):
        retval = "["
        for u in v:
            retval += " " + str(self.dump_value(u)) + ","
        retval += "]"
        return retval

    def dump_inline_table(self, section):
        """Preserve inline table in its compact syntax instead of expanding
        into subsection.

        https://github.com/toml-lang/toml#user-content-inline-table
        """
        retval = ""
        if isinstance(section, dict):
            val_list = []
            for k, v in section.items():
                val = self.dump_inline_table(v)
                val_list.append(k + " = " + val)
            retval += "{ " + ", ".join(val_list) + " }\n"
            return retval
        else:
            return str(self.dump_value(section))

    def dump_value(self, v):
        """Dump value using registered dump functions.

        Dump functions can be registered in a two ways:
        * strictly by type: add function by type to TomlEncoder.dump_by_type.
          They will be used for matching by type(value) only.
        * by checking with isinstance: add function by type to
          TomlEncoder.dump_by_instance.
        """

        dump_fn = self.get_dump_function(v)
        return dump_fn(v)

    def dump_sections(self, o, sup):
        retstr = ""
        if sup != "" and sup[-1] != ".":
            sup += '.'
        retdict = self._dict()
        arraystr = ""
        for section in o:
            section = str(section)
            qsection = section
            if not re.match(r'^[A-Za-z0-9_-]+$', section):
                qsection = _dump_str(section)
            if not isinstance(o[section], dict):
                arrayoftables = False
                if isinstance(o[section], list):
                    for a in o[section]:
                        if isinstance(a, dict):
                            arrayoftables = True
                if arrayoftables:
                    for a in o[section]:
                        arraytabstr = "\n"
                        arraystr += "[[" + sup + qsection + "]]\n"
                        s, d = self.dump_sections(a, sup + qsection)
                        if s:
                            if s[0] == "[":
                                arraytabstr += s
                            else:
                                arraystr += s
                        while d:
                            newd = self._dict()
                            for dsec in d:
                                s1, d1 = self.dump_sections(d[dsec], sup +
                                                            qsection + "." +
                                                            dsec)
                                if s1:
                                    arraytabstr += ("[" + sup + qsection +
                                                    "." + dsec + "]\n")
                                    arraytabstr += s1
                                for s1 in d1:
                                    newd[dsec + "." + s1] = d1[s1]
                            d = newd
                        arraystr += arraytabstr
                else:
                    if o[section] is not None:
                        retstr += (qsection + " = " +
                                   str(self.dump_value(o[section])) + '\n')
            elif self.preserve and isinstance(o[section], InlineTableDict):
                retstr += (qsection + " = " +
                           self.dump_inline_table(o[section]))
            else:
                retdict[qsection] = o[section]
        retstr += arraystr
        return (retstr, retdict)


class TomlPreserveInlineDictEncoder(TomlEncoder):

    def __init__(self, _dict=dict):
        super().__init__(_dict, True)


class TomlArraySeparatorEncoder(TomlEncoder):

    def __init__(self, _dict=dict, preserve=False, separator=","):
        super().__init__(_dict, preserve)
        if separator.strip() == "":
            separator = "," + separator
        elif separator.strip(' \t\n\r,'):
            raise ValueError("Invalid separator for arrays")
        self.separator = separator

    def dump_list(self, v):
        t = []
        retval = "["
        for u in v:
            t.append(self.dump_value(u))
        while t != []:
            s = []
            for u in t:
                if isinstance(u, list):
                    for r in u:
                        s.append(r)
                else:
                    retval += " " + str(u) + self.separator
            t = s
        retval += "]"
        return retval


class TomlNumpyEncoder(TomlEncoder):

    def __init__(self, _dict=dict, preserve=False):
        import numpy as np
        super().__init__(_dict, preserve)
        self.dump_by_type[np.float16] = _dump_float
        self.dump_by_type[np.float32] = _dump_float
        self.dump_by_type[np.float64] = _dump_float
        self.dump_by_type[np.int16] = self._dump_int
        self.dump_by_type[np.int32] = self._dump_int
        self.dump_by_type[np.int64] = self._dump_int

    def _dump_int(self, v):
        return "{}".format(int(v))


class TomlPreserveCommentEncoder(TomlEncoder):

    def __init__(self, _dict=dict, preserve=False):
        from toml.decoder import CommentValue
        super().__init__(_dict, preserve)
        self.dump_by_type[CommentValue] = lambda v: v.dump(self.dump_value)
