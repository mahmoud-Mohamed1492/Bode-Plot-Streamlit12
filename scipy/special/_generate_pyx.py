#!/usr/bin/env python3
"""
python _generate_pyx.py

Generate Ufunc definition source files for scipy.special. Produces
files '_ufuncs.c' and '_ufuncs_cxx.c' by first producing Cython.

This will generate both calls to PyUFunc_FromFuncAndData and the
required ufunc inner loops.

The functions signatures are contained in 'functions.json', the syntax
for a function signature is

    <function>:       <name> ':' <input> '*' <output>
                        '->' <retval> '*' <ignored_retval>
    <input>:          <typecode>*
    <output>:         <typecode>*
    <retval>:         <typecode>?
    <ignored_retval>: <typecode>?
    <headers>:        <header_name> [',' <header_name>]*

The input parameter types are denoted by single character type
codes, according to

   'f': 'float'
   'd': 'double'
   'g': 'long double'
   'F': 'float complex'
   'D': 'double complex'
   'G': 'long double complex'
   'i': 'int'
   'l': 'long'
   'p': 'npy_intp', 'Py_ssize_t'
   'v': 'void'

If multiple kernel functions are given for a single ufunc, the one
which is used is determined by the standard ufunc mechanism. Kernel
functions that are listed first are also matched first against the
ufunc input types, so functions listed earlier take precedence.

In addition, versions with casted variables, such as d->f,D->F and
i->d are automatically generated.

There should be either a single header that contains all of the kernel
functions listed, or there should be one header for each kernel
function. Cython pxd files are allowed in addition to .h files.

Cython functions may use fused types, but the names in the list
should be the specialized ones, such as 'somefunc[float]'.

Function coming from C++ should have ``++`` appended to the name of
the header.

Floating-point exceptions inside these Ufuncs are converted to
special function errors --- which are separately controlled by the
user, and off by default, as they are usually not especially useful
for the user.


The C++ module
--------------
In addition to ``_ufuncs`` module, a second module ``_ufuncs_cxx`` is
generated. This module only exports function pointers that are to be
used when constructing some of the ufuncs in ``_ufuncs``. The function
pointers are exported via Cython's standard mechanism.

This mainly avoids build issues --- Python distutils has no way to
figure out what to do if you want to link both C++ and Fortran code in
the same shared library.

"""

import json
import os
from stat import ST_MTIME
import argparse
import re
import textwrap

special_ufuncs = [
    '_cospi', '_lambertw', '_scaled_exp1', '_sinpi', '_spherical_jn', '_spherical_jn_d',
    '_spherical_yn', '_spherical_yn_d', '_spherical_in', '_spherical_in_d',
    '_spherical_kn', '_spherical_kn_d', 'airy', 'airye', 'bei', 'beip', 'ber', 'berp',
    'binom', 'exp1', 'expi', 'expit', 'exprel', 'gamma', 'gammaln', 'hankel1',
    'hankel1e', 'hankel2', 'hankel2e', 'hyp2f1', 'it2i0k0', 'it2j0y0', 'it2struve0',
    'itairy', 'iti0k0', 'itj0y0', 'itmodstruve0', 'itstruve0',
    'iv', '_iv_ratio', 'ive', 'jv',
    'jve', 'kei', 'keip', 'kelvin', 'ker', 'kerp', 'kv', 'kve', 'log_expit',
    'log_wright_bessel', 'loggamma', 'logit', 'mathieu_a', 'mathieu_b', 'mathieu_cem',
    'mathieu_modcem1', 'mathieu_modcem2', 'mathieu_modsem1', 'mathieu_modsem2',
    'mathieu_sem', 'modfresnelm', 'modfresnelp', 'obl_ang1', 'obl_ang1_cv', 'obl_cv',
    'obl_rad1', 'obl_rad1_cv', 'obl_rad2', 'obl_rad2_cv', 'pbdv', 'pbvv', 'pbwa',
    'pro_ang1', 'pro_ang1_cv', 'pro_cv', 'pro_rad1', 'pro_rad1_cv', 'pro_rad2',
    'pro_rad2_cv', 'psi', 'rgamma', 'sph_harm', 'wright_bessel', 'yv', 'yve', '_zeta'
]

# -----------------------------------------------------------------------------
# Extra code
# -----------------------------------------------------------------------------

UFUNCS_EXTRA_CODE_COMMON = """\
# This file is automatically generated by _generate_pyx.py.
# Do not edit manually!

from libc.math cimport NAN

include "_ufuncs_extra_code_common.pxi"
"""

UFUNCS_EXTRA_CODE = """\
include "_ufuncs_extra_code.pxi"
"""

UFUNCS_EXTRA_CODE_BOTTOM = f"""\
from ._special_ufuncs import ({', '.join(special_ufuncs)})

#
# Aliases
#
jn = jv
"""

STUBS = """\
# This file is automatically generated by _generate_pyx.py.
# Do not edit manually!

from typing import Any, Dict

import numpy as np

__all__ = [
    'geterr',
    'seterr',
    'errstate',
    {ALL}
]

def geterr() -> Dict[str, str]: ...
def seterr(**kwargs: str) -> Dict[str, str]: ...

class errstate:
    def __init__(self, **kargs: str) -> None: ...
    def __enter__(self) -> None: ...
    def __exit__(
        self,
        exc_type: Any,  # Unused
        exc_value: Any,  # Unused
        traceback: Any,  # Unused
    ) -> None: ...

{STUBS}

"""


# -----------------------------------------------------------------------------
# Code generation
# -----------------------------------------------------------------------------


BASE_DIR = os.path.abspath(os.path.dirname(__file__))

add_newdocs = __import__('_add_newdocs')

CY_TYPES = {
    'f': 'float',
    'd': 'double',
    'g': 'long double',
    'F': 'float complex',
    'D': 'double complex',
    'G': 'long double complex',
    'i': 'int',
    'l': 'long',
    'p': 'Py_ssize_t',
    'v': 'void',
}

C_TYPES = {
    'f': 'npy_float',
    'd': 'npy_double',
    'g': 'npy_longdouble',
    'F': 'npy_cfloat',
    'D': 'npy_cdouble',
    'G': 'npy_clongdouble',
    'i': 'npy_int',
    'l': 'npy_long',
    'p': 'npy_intp',
    'v': 'void',
}

TYPE_NAMES = {
    'f': 'NPY_FLOAT',
    'd': 'NPY_DOUBLE',
    'g': 'NPY_LONGDOUBLE',
    'F': 'NPY_CFLOAT',
    'D': 'NPY_CDOUBLE',
    'G': 'NPY_CLONGDOUBLE',
    'i': 'NPY_INT',
    'l': 'NPY_LONG',
    'p': 'NPY_INTP',
}


def underscore(arg):
    return arg.replace(" ", "_")


def cast_order(c):
    return ['ilpfdgFDG'.index(x) for x in c]


# These downcasts will cause the function to return NaNs, unless the
# values happen to coincide exactly.
DANGEROUS_DOWNCAST = {
    ('F', 'i'), ('F', 'l'), ('F', 'p'), ('F', 'f'), ('F', 'd'), ('F', 'g'),
    ('D', 'i'), ('D', 'l'), ('D', 'p'), ('D', 'f'), ('D', 'd'), ('D', 'g'),
    ('G', 'i'), ('G', 'l'), ('G', 'p'), ('G', 'f'), ('G', 'd'), ('G', 'g'),
    ('f', 'i'), ('f', 'l'), ('f', 'p'),
    ('d', 'i'), ('d', 'l'), ('d', 'p'),
    ('g', 'i'), ('g', 'l'), ('g', 'p'),
    ('p', 'l'), ('p', 'i'),
    ('l', 'i'),
}

NAN_VALUE = {
    'f': 'NAN',
    'd': 'NAN',
    'g': 'NAN',
    'F': 'NAN',
    'D': 'NAN',
    'G': 'NAN',
    'i': '0xbad0bad0',
    'l': '0xbad0bad0',
    'p': '0xbad0bad0',
}


def generate_loop(func_inputs, func_outputs, func_retval,
                  ufunc_inputs, ufunc_outputs):
    """
    Generate a UFunc loop function that calls a function given as its
    data parameter with the specified input and output arguments and
    return value.

    This function can be passed to PyUFunc_FromFuncAndData.

    Parameters
    ----------
    func_inputs, func_outputs, func_retval : str
        Signature of the function to call, given as type codes of the
        input, output and return value arguments. These 1-character
        codes are given according to the CY_TYPES and TYPE_NAMES
        lists above.

        The corresponding C function signature to be called is:

            retval func(intype1 iv1, intype2 iv2, ..., outtype1 *ov1, ...);

        If len(ufunc_outputs) == len(func_outputs)+1, the return value
        is treated as the first output argument. Otherwise, the return
        value is ignored.

    ufunc_inputs, ufunc_outputs : str
        Ufunc input and output signature.

        This does not have to exactly match the function signature,
        as long as the type casts work out on the C level.

    Returns
    -------
    loop_name
        Name of the generated loop function.
    loop_body
        Generated C code for the loop.

    """
    if len(func_inputs) != len(ufunc_inputs):
        raise ValueError("Function and ufunc have different number of inputs")

    if len(func_outputs) != len(ufunc_outputs) and not (
            func_retval != "v" and len(func_outputs)+1 == len(ufunc_outputs)):
        raise ValueError("Function retval and ufunc outputs don't match")

    name = (f"loop_{func_retval}_{func_inputs}_{func_outputs}"
            f"_As_{ufunc_inputs}_{ufunc_outputs}")
    body = (f"cdef void {name}(char **args, np.npy_intp *dims, np.npy_intp *steps, "
            f"void *data) noexcept nogil:\n")
    body += "    cdef np.npy_intp i, n = dims[0]\n"
    body += "    cdef void *func = (<void**>data)[0]\n"
    body += "    cdef char *func_name = <char*>(<void**>data)[1]\n"

    for j in range(len(ufunc_inputs)):
        body += "    cdef char *ip%d = args[%d]\n" % (j, j)
    for j in range(len(ufunc_outputs)):
        body += "    cdef char *op%d = args[%d]\n" % (j, j + len(ufunc_inputs))

    ftypes = []
    fvars = []
    outtypecodes = []
    for j in range(len(func_inputs)):
        ftypes.append(CY_TYPES[func_inputs[j]])
        fvars.append("<%s>(<%s*>ip%d)[0]" % (
            CY_TYPES[func_inputs[j]],
            CY_TYPES[ufunc_inputs[j]], j))

    if len(func_outputs)+1 == len(ufunc_outputs):
        func_joff = 1
        outtypecodes.append(func_retval)
        body += f"    cdef {CY_TYPES[func_retval]} ov0\n"
    else:
        func_joff = 0

    for j, outtype in enumerate(func_outputs):
        body += "    cdef %s ov%d\n" % (CY_TYPES[outtype], j+func_joff)
        ftypes.append("%s *" % CY_TYPES[outtype])
        fvars.append("&ov%d" % (j+func_joff))
        outtypecodes.append(outtype)

    body += "    for i in range(n):\n"
    if len(func_outputs)+1 == len(ufunc_outputs):
        rv = "ov0 = "
    else:
        rv = ""

    funcall = "        {}(<{}(*)({}) noexcept nogil>func)({})\n".format(
        rv, CY_TYPES[func_retval], ", ".join(ftypes), ", ".join(fvars))

    # Cast-check inputs and call function
    input_checks = []
    for j in range(len(func_inputs)):
        if (ufunc_inputs[j], func_inputs[j]) in DANGEROUS_DOWNCAST:
            chk = "<%s>(<%s*>ip%d)[0] == (<%s*>ip%d)[0]" % (
                CY_TYPES[func_inputs[j]], CY_TYPES[ufunc_inputs[j]], j,
                CY_TYPES[ufunc_inputs[j]], j)
            input_checks.append(chk)

    if input_checks:
        body += "        if %s:\n" % (" and ".join(input_checks))
        body += "    " + funcall
        body += "        else:\n"
        body += ("            sf_error.error(func_name, sf_error.DOMAIN, "
                 "\"invalid input argument\")\n")
        for j, outtype in enumerate(outtypecodes):
            body += "            ov%d = <%s>%s\n" % (
                j, CY_TYPES[outtype], NAN_VALUE[outtype])
    else:
        body += funcall

    # Assign and cast-check output values
    for j, (outtype, fouttype) in enumerate(zip(ufunc_outputs, outtypecodes)):
        if (fouttype, outtype) in DANGEROUS_DOWNCAST:
            body += "        if ov%d == <%s>ov%d:\n" % (j, CY_TYPES[outtype], j)
            body += "            (<%s *>op%d)[0] = <%s>ov%d\n" % (
                CY_TYPES[outtype], j, CY_TYPES[outtype], j)
            body += "        else:\n"
            body += ("            sf_error.error(func_name, sf_error.DOMAIN, "
                     "\"invalid output\")\n")
            body += "            (<%s *>op%d)[0] = <%s>%s\n" % (
                CY_TYPES[outtype], j, CY_TYPES[outtype], NAN_VALUE[outtype])
        else:
            body += "        (<%s *>op%d)[0] = <%s>ov%d\n" % (
                CY_TYPES[outtype], j, CY_TYPES[outtype], j)
    for j in range(len(ufunc_inputs)):
        body += "        ip%d += steps[%d]\n" % (j, j)
    for j in range(len(ufunc_outputs)):
        body += "        op%d += steps[%d]\n" % (j, j + len(ufunc_inputs))

    body += "    sf_error.check_fpe(func_name)\n"

    return name, body


def iter_variants(inputs, outputs):
    """
    Generate variants of UFunc signatures, by changing variable types,
    within the limitation that the corresponding C types casts still
    work out.

    This does not generate all possibilities, just the ones required
    for the ufunc to work properly with the most common data types.

    Parameters
    ----------
    inputs, outputs : str
        UFunc input and output signature strings

    Yields
    ------
    new_input, new_output : str
        Modified input and output strings.
        Also the original input/output pair is yielded.

    """
    maps = [
        # always use long instead of int (more common type on 64-bit)
        ('i', 'l'),
    ]

    # float32-preserving signatures
    if not ('i' in inputs or 'l' in inputs or 'q' in inputs
             or 'p' in inputs):
        # Don't add float32 versions of ufuncs with integer arguments, as this
        # can lead to incorrect dtype selection if the integer arguments are
        # arrays, but float arguments are scalars.
        # For instance sph_harm(0,[0],0,0).dtype == complex64
        # This may be a NumPy bug, but we need to work around it.
        # cf. gh-4895, https://github.com/numpy/numpy/issues/5895
        maps = maps + [(a + 'dD', b + 'fF') for a, b in maps]

    # do the replacements
    for src, dst in maps:
        new_inputs = inputs
        new_outputs = outputs
        for a, b in zip(src, dst):
            new_inputs = new_inputs.replace(a, b)
            new_outputs = new_outputs.replace(a, b)
        yield new_inputs, new_outputs


class Func:
    """
    Base class for Ufunc.

    """
    def __init__(self, name, signatures):
        self.name = name
        self.signatures = []
        self.function_name_overrides = {}

        for header in signatures.keys():
            for name, sig in signatures[header].items():
                inarg, outarg, ret = self._parse_signature(sig)
                self.signatures.append((name, inarg, outarg, ret, header))

    def _parse_signature(self, sig):
        T = 'fdgFDGilp'
        m = re.match(rf"\s*([{T}]*)\s*\*\s*([{T}]*)\s*->\s*([*{T}]*)\s*$",
                     sig)
        if m:
            inarg, outarg, ret = (x.strip() for x in m.groups())
            if ret.count('*') > 1:
                raise ValueError(f"{self.name}: Invalid signature: {sig}")
            return inarg, outarg, ret
        m = re.match(rf"\s*([{T}]*)\s*->\s*([{T}]?)\s*$", sig)
        if m:
            inarg, ret = (x.strip() for x in m.groups())
            return inarg, "", ret
        raise ValueError(f"{self.name}: Invalid signature: {sig}")

    def get_prototypes(self, nptypes_for_h=False):
        prototypes = []
        for func_name, inarg, outarg, ret, header in self.signatures:
            ret = ret.replace('*', '')
            c_args = ([C_TYPES[x] for x in inarg]
                      + [C_TYPES[x] + ' *' for x in outarg])
            cy_args = ([CY_TYPES[x] for x in inarg]
                       + [CY_TYPES[x] + ' *' for x in outarg])
            c_proto = "{} (*)({})".format(C_TYPES[ret], ", ".join(c_args))
            if header.endswith("h") and nptypes_for_h:
                cy_proto = c_proto + "nogil"
            else:
                cy_proto = ("{} (*)({}) noexcept nogil"
                            .format(CY_TYPES[ret], ", ".join(cy_args)))
            prototypes.append((func_name, c_proto, cy_proto, header))
        return prototypes

    def cython_func_name(self, c_name, specialized=False, prefix="_func_",
                         override=True):
        # act on function name overrides
        if override and c_name in self.function_name_overrides:
            c_name = self.function_name_overrides[c_name]
            prefix = ""

        # support fused types
        m = re.match(r'^(.*?)(\[.*\])$', c_name)
        if m:
            c_base_name, fused_part = m.groups()
        else:
            c_base_name, fused_part = c_name, ""
        if specialized:
            return "{}{}{}".format(prefix, c_base_name, fused_part.replace(' ', '_'))
        else:
            return f"{prefix}{c_base_name}"


class Ufunc(Func):
    """
    Ufunc signature, restricted format suitable for special functions.

    Parameters
    ----------
    name
        Name of the ufunc to create
    signature
        String of form 'func: fff*ff->f, func2: ddd->*i' describing
        the C-level functions and types of their input arguments
        and return values.

        The syntax is
        'function_name: inputparams*outputparams->output_retval*ignored_retval'

    Attributes
    ----------
    name : str
        Python name for the Ufunc
    signatures : list of (func_name, inarg_spec, outarg_spec, ret_spec, header_name)
        List of parsed signatures
    doc : str
        Docstring, obtained from add_newdocs
    function_name_overrides : dict of str->str
        Overrides for the function names in signatures

    """
    def __init__(self, name, signatures):
        super().__init__(name, signatures)
        self.doc = add_newdocs.get(name)
        if self.doc is None:
            raise ValueError("No docstring for ufunc %r" % name)
        self.doc = textwrap.dedent(self.doc).strip()

    def _get_signatures_and_loops(self, all_loops):
        inarg_num = None
        outarg_num = None

        seen = set()
        variants = []

        def add_variant(func_name, inarg, outarg, ret, inp, outp):
            if inp in seen:
                return
            seen.add(inp)

            sig = (func_name, inp, outp)
            if "v" in outp:
                raise ValueError(f"{self.name}: void signature {sig!r}")
            if len(inp) != inarg_num or len(outp) != outarg_num:
                raise ValueError(
                    "%s: signature %r does not have %d/%d input/output args" % (
                        self.name, sig, inarg_num, outarg_num
                    )
                )

            loop_name, loop = generate_loop(inarg, outarg, ret, inp, outp)
            all_loops[loop_name] = loop
            variants.append((func_name, loop_name, inp, outp))

        # First add base variants
        for func_name, inarg, outarg, ret, header in self.signatures:
            outp = re.sub(r'\*.*', '', ret) + outarg
            ret = ret.replace('*', '')
            if inarg_num is None:
                inarg_num = len(inarg)
                outarg_num = len(outp)

            inp, outp = list(iter_variants(inarg, outp))[0]
            add_variant(func_name, inarg, outarg, ret, inp, outp)

        # Then the supplementary ones
        for func_name, inarg, outarg, ret, header in self.signatures:
            outp = re.sub(r'\*.*', '', ret) + outarg
            ret = ret.replace('*', '')
            for inp, outp in iter_variants(inarg, outp):
                add_variant(func_name, inarg, outarg, ret, inp, outp)

        # Then sort variants to input argument cast order
        # -- the sort is stable, so functions earlier in the signature list
        #    are still preferred
        variants.sort(key=lambda v: cast_order(v[2]))

        return variants, inarg_num, outarg_num

    def generate(self, all_loops):
        toplevel = ""

        variants, inarg_num, outarg_num = self._get_signatures_and_loops(
                all_loops)

        loops = []
        funcs = []
        types = []

        for func_name, loop_name, inputs, outputs in variants:
            for x in inputs:
                types.append(TYPE_NAMES[x])
            for x in outputs:
                types.append(TYPE_NAMES[x])
            loops.append(loop_name)
            funcs.append(func_name)

        toplevel += ("cdef np.PyUFuncGenericFunction ufunc_%s_loops[%d]\n" %
                     (self.name, len(loops)))
        toplevel += "cdef void *ufunc_%s_ptr[%d]\n" % (self.name, 2*len(funcs))
        toplevel += "cdef void *ufunc_%s_data[%d]\n" % (self.name, len(funcs))
        toplevel += "cdef char ufunc_%s_types[%d]\n" % (self.name, len(types))
        toplevel += 'cdef char *ufunc_{}_doc = (\n    "{}")\n'.format(
            self.name,
            self.doc.replace("\\", "\\\\").replace('"', '\\"')
            .replace('\n', '\\n\"\n    "')
        )

        for j, function in enumerate(loops):
            toplevel += ("ufunc_%s_loops[%d] = <np.PyUFuncGenericFunction>%s\n" %
                         (self.name, j, function))
        for j, type in enumerate(types):
            toplevel += "ufunc_%s_types[%d] = <char>%s\n" % (self.name, j, type)
        for j, func in enumerate(funcs):
            toplevel += "ufunc_%s_ptr[2*%d] = <void*>%s\n" % (
                self.name, j, self.cython_func_name(func, specialized=True)
            )
            toplevel += "ufunc_%s_ptr[2*%d+1] = <void*>(<char*>\"%s\")\n" % (
                self.name, j, self.name
            )
        for j, func in enumerate(funcs):
            toplevel += "ufunc_%s_data[%d] = &ufunc_%s_ptr[2*%d]\n" % (
                self.name, j, self.name, j)

        toplevel += ('@ = np.PyUFunc_FromFuncAndData(ufunc_@_loops, '
                     'ufunc_@_data, ufunc_@_types, %d, %d, %d, 0, '
                     '"@", ufunc_@_doc, 0)\n' % (len(types)/(inarg_num+outarg_num),
                                                 inarg_num, outarg_num)
                     ).replace('@', self.name)

        return toplevel


def get_declaration(ufunc, c_name, c_proto, cy_proto, header,
                    proto_h_filename):
    """
    Construct a Cython declaration of a function coming either from a
    pxd or a header file. Do sufficient tricks to enable compile-time
    type checking against the signature expected by the ufunc.

    """
    defs = []
    defs_h = []

    var_name = c_name.replace('[', '_').replace(']', '_').replace(' ', '_')

    if header.endswith('.pxd'):
        defs.append("from .{} cimport {} as {}".format(
            header[:-4], ufunc.cython_func_name(c_name, prefix=""),
            ufunc.cython_func_name(c_name)))

        # check function signature at compile time
        proto_name = '_proto_%s_t' % var_name
        defs.append("ctypedef %s" % (cy_proto.replace('(*)', proto_name)))
        defs.append(f"cdef {proto_name} *{proto_name}_var = "
                    f"&{ufunc.cython_func_name(c_name, specialized=True)}")
    else:
        # redeclare the function, so that the assumed
        # signature is checked at compile time
        new_name = f"{ufunc.cython_func_name(c_name)} \"{c_name}\""
        proto_h_filename = os.path.basename(proto_h_filename)
        defs.append(f'cdef extern from r"{proto_h_filename}":')
        defs.append("    cdef %s" % (cy_proto.replace('(*)', new_name)))
        defs_h.append(f'#include "{header}"')
        defs_h.append("%s;" % (c_proto.replace('(*)', c_name)))

    return defs, defs_h, var_name


def generate_ufuncs(fn_prefix, cxx_fn_prefix, ufuncs):
    filename = fn_prefix + ".pyx"
    proto_h_filename = fn_prefix + '_defs.h'

    cxx_proto_h_filename = cxx_fn_prefix + '_defs.h'
    cxx_pyx_filename = cxx_fn_prefix + ".pyx"
    cxx_pxd_filename = cxx_fn_prefix + ".pxd"

    toplevel = ""

    # for _ufuncs*
    defs = []
    defs_h = []
    all_loops = {}

    # for _ufuncs_cxx*
    cxx_defs = []
    cxx_pxd_defs = [
        "from . cimport sf_error",
        "cdef void _set_action(sf_error.sf_error_t, sf_error.sf_action_t) "
        "noexcept nogil"
    ]
    cxx_defs_h = []

    ufuncs.sort(key=lambda u: u.name)

    for ufunc in ufuncs:
        # generate function declaration and type checking snippets
        cfuncs = ufunc.get_prototypes()
        for c_name, c_proto, cy_proto, header in cfuncs:
            if header.endswith('++'):
                header = header[:-2]

                # for the CXX module
                item_defs, item_defs_h, var_name = get_declaration(
                    ufunc, c_name, c_proto, cy_proto, header, cxx_proto_h_filename
                )
                cxx_defs.extend(item_defs)
                cxx_defs_h.extend(item_defs_h)

                func_name = ufunc.cython_func_name(
                    c_name, specialized=True, override=False
                )
                cxx_defs.append(f"cdef void *_export_{var_name} = <void*>{func_name}")
                cxx_pxd_defs.append(f"cdef void *_export_{var_name}")

                # let cython grab the function pointer from the c++ shared library
                ufunc.function_name_overrides[c_name] = (
                    "scipy.special._ufuncs_cxx._export_" + var_name
                )
            else:
                # usual case
                item_defs, item_defs_h, _ = get_declaration(
                    ufunc, c_name, c_proto, cy_proto, header, proto_h_filename
                )
                defs.extend(item_defs)
                defs_h.extend(item_defs_h)

        # ufunc creation code snippet
        t = ufunc.generate(all_loops)
        toplevel += t + "\n"

    # Produce output
    toplevel = "\n".join(sorted(all_loops.values()) + defs + [toplevel])
    # Generate an `__all__` for the module
    all_ufuncs = (
        [
            f"'{ufunc.name}'"
            for ufunc in ufuncs if not ufunc.name.startswith('_')
        ]
        + ["'geterr'", "'seterr'", "'errstate'", "'jn'"] +
        [
            f"'{name}'"
            for name in special_ufuncs if not name.startswith('_')
        ]
    )
    module_all = '__all__ = [{}]'.format(', '.join(all_ufuncs))

    with open(filename, 'w') as f:
        f.write(UFUNCS_EXTRA_CODE_COMMON)
        f.write(UFUNCS_EXTRA_CODE)
        f.write(module_all)
        f.write("\n")
        f.write(toplevel)
        f.write(UFUNCS_EXTRA_CODE_BOTTOM)

    defs_h = unique(defs_h)
    with open(proto_h_filename, 'w') as f:
        f.write("#ifndef UFUNCS_PROTO_H\n#define UFUNCS_PROTO_H 1\n")
        f.write("\n".join(defs_h))
        f.write("\n#endif\n")

    cxx_defs_h = unique(cxx_defs_h)
    with open(cxx_proto_h_filename, 'w') as f:
        f.write("#ifndef UFUNCS_PROTO_H\n#define UFUNCS_PROTO_H 1\n")
        f.write("\n".join(cxx_defs_h))
        f.write("\n#endif\n")

    with open(cxx_pyx_filename, 'w') as f:
        f.write(UFUNCS_EXTRA_CODE_COMMON)
        f.write("\n")
        f.write("\n".join(cxx_defs))

    with open(cxx_pxd_filename, 'w') as f:
        f.write("\n".join(cxx_pxd_defs))


def unique(lst):
    """
    Return a list without repeated entries (first occurrence is kept),
    preserving order.
    """
    seen = set()
    new_lst = []
    for item in lst:
        if item in seen:
            continue
        seen.add(item)
        new_lst.append(item)
    return new_lst


def newer(source, target):
    """
    Return true if 'source' exists and is more recently modified than
    'target', or if 'source' exists and 'target' doesn't.  Return false if
    both exist and 'target' is the same age or younger than 'source'.
    """
    if not os.path.exists(source):
        raise ValueError("file '%s' does not exist" % os.path.abspath(source))
    if not os.path.exists(target):
        return 1

    mtime1 = os.stat(source)[ST_MTIME]
    mtime2 = os.stat(target)[ST_MTIME]

    return mtime1 > mtime2


def all_newer(src_files, dst_files):
    return all(os.path.exists(dst) and newer(dst, src)
               for dst in dst_files for src in src_files)


def main(outdir):
    pwd = os.path.dirname(__file__)
    src_files = (os.path.abspath(__file__),
                 os.path.abspath(os.path.join(pwd, 'functions.json')),
                 os.path.abspath(os.path.join(pwd, '_add_newdocs.py')))
    dst_files = ('_ufuncs.pyx',
                 '_ufuncs_defs.h',
                 '_ufuncs_cxx.pyx',
                 '_ufuncs_cxx.pxd',
                 '_ufuncs_cxx_defs.h')
    dst_files = (os.path.join(outdir, f) for f in dst_files)

    os.chdir(BASE_DIR)

    if all_newer(src_files, dst_files):
        print("scipy/special/_generate_pyx.py: all files up-to-date")
        return

    ufuncs = []
    with open('functions.json') as data:
        functions = json.load(data)
    for f, sig in functions.items():
        if (f not in special_ufuncs):
            ufuncs.append(Ufunc(f, sig))
    generate_ufuncs(os.path.join(outdir, "_ufuncs"),
                    os.path.join(outdir, "_ufuncs_cxx"),
                    ufuncs)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-o", "--outdir", type=str,
                        help="Path to the output directory")
    args = parser.parse_args()

    if not args.outdir:
        raise ValueError("Missing `--outdir` argument to _generate_pyx.py")
    else:
        outdir_abs = os.path.join(os.getcwd(), args.outdir)

    main(outdir_abs)
