.. _amdgpu-amdhsa-function-call-convention:

Call Convention
~~~~~~~~~~~~~~~

.. note::

  This section is currently incomplete and has inaccuracies. It is WIP that will
  be updated as information is determined.

See :ref:`amdgpu-dwarf-address-space-identifier` for information on swizzled
addresses. Unswizzled addresses are normal linear addresses.

.. _amdgpu-amdhsa-function-call-convention-kernel-functions:

Kernel Functions
++++++++++++++++

This section describes the call convention ABI for the outer kernel function.

See :ref:`amdgpu-amdhsa-initial-kernel-execution-state` for the kernel call
convention.

The following is not part of the AMDGPU kernel calling convention but describes
how the AMDGPU implements function calls:

1.  Clang decides the kernarg layout to match the *HSA Programmer's Language
    Reference* [HSA]_.

    - All structs are passed directly.
    - Lambda values are passed *TBA*.

    .. TODO::

      - Does this really follow HSA rules? Or are structs >16 bytes passed
        by-value struct?
      - What is ABI for lambda values?

4.  The kernel performs certain setup in its prolog, as described in
    :ref:`amdgpu-amdhsa-kernel-prolog`.

.. _amdgpu-amdhsa-function-call-convention-non-kernel-functions:

Non-Kernel Functions
++++++++++++++++++++

This section describes the call convention ABI for functions other than the
outer kernel function.

If a kernel has function calls then scratch is always allocated and used for
the call stack which grows from low address to high address using the swizzled
scratch address space.

On entry to a function:

#.  SGPR0-3 contain a V# with the following properties (see
    :ref:`amdgpu-amdhsa-kernel-prolog-private-segment-buffer`):

    * Base address pointing to the beginning of the wavefront scratch backing
      memory.
    * Swizzled with dword element size and stride of wavefront size elements.

#.  The FLAT_SCRATCH register pair is setup. See
    :ref:`amdgpu-amdhsa-kernel-prolog-flat-scratch`.
#.  GFX6-GFX8: M0 register set to the size of LDS in bytes. See
    :ref:`amdgpu-amdhsa-kernel-prolog-m0`.
#.  The EXEC register is set to the lanes active on entry to the function.
#.  MODE register: *TBD*
#.  VGPR0-31 and SGPR4-29 are used to pass function input arguments as described
    below.
#.  SGPR30-31 return address (RA). The code address that the function must
    return to when it completes. The value is undefined if the function is *no
    return*.
#.  SGPR32 is used for the stack pointer (SP). It is an unswizzled scratch
    offset relative to the beginning of the wavefront scratch backing memory.

    The unswizzled SP can be used with buffer instructions as an unswizzled SGPR
    offset with the scratch V# in SGPR0-3 to access the stack in a swizzled
    manner.

    The unswizzled SP value can be converted into the swizzled SP value by:

      | swizzled SP = unswizzled SP / wavefront size

    This may be used to obtain the private address space address of stack
    objects and to convert this address to a flat address by adding the flat
    scratch aperture base address.

    The swizzled SP value is always 4 bytes aligned for the ``r600``
    architecture and 16 byte aligned for the ``amdgcn`` architecture.

    .. note::

      The ``amdgcn`` value is selected to avoid dynamic stack alignment for the
      OpenCL language which has the largest base type defined as 16 bytes.

    On entry, the swizzled SP value is the address of the first function
    argument passed on the stack. Other stack passed arguments are positive
    offsets from the entry swizzled SP value.

    The function may use positive offsets beyond the last stack passed argument
    for stack allocated local variables and register spill slots. If necessary,
    the function may align these to greater alignment than 16 bytes. After these
    the function may dynamically allocate space for such things as runtime sized
    ``alloca`` local allocations.

    If the function calls another function, it will place any stack allocated
    arguments after the last local allocation and adjust SGPR32 to the address
    after the last local allocation.

#. All other registers are unspecified.
#. Any necessary ``s_waitcnt`` has been performed to ensure memory is available
   to the function.
#. Use pass-by-reference (byref) in stead of pass-by-value (byval) for struct
   arguments in C ABI. Callee is responsible for allocating stack memory and
   copying the value of the struct if modified. Note that the backend still
   supports byval for struct arguments.

On exit from a function:

#.  VGPR0-31 and SGPR4-29 are used to pass function result arguments as
    described below. Any registers used are considered clobbered registers.
#.  The following registers are preserved and have the same value as on entry:

    * FLAT_SCRATCH
    * EXEC
    * GFX6-GFX8: M0
    * All SGPR registers except the clobbered registers of SGPR4-31.
    * VGPR40-47
    * VGPR56-63
    * VGPR72-79
    * VGPR88-95
    * VGPR104-111
    * VGPR120-127
    * VGPR136-143
    * VGPR152-159
    * VGPR168-175
    * VGPR184-191
    * VGPR200-207
    * VGPR216-223
    * VGPR232-239
    * VGPR248-255

        .. note::

          Except the argument registers, the VGPRs clobbered and the preserved
          registers are intermixed at regular intervals in order to keep a
          similar ratio independent of the number of allocated VGPRs.

    * GFX90A: All AGPR registers except the clobbered registers AGPR0-31.
    * Lanes of all VGPRs that are inactive at the call site.

      For the AMDGPU backend, an inter-procedural register allocation (IPRA)
      optimization may mark some of clobbered SGPR and VGPR registers as
      preserved if it can be determined that the called function does not change
      their value.

#.  The PC is set to the RA provided on entry.
#.  MODE register: *TBD*.
#.  All other registers are clobbered.
#.  Any necessary ``s_waitcnt`` has been performed to ensure memory accessed by
    function is available to the caller.

.. TODO::

  - How are function results returned? The address of structured types is passed
    by reference, but what about other types?

The function input arguments are made up of the formal arguments explicitly
declared by the source language function plus the implicit input arguments used
by the implementation.

The source language input arguments are:

1. Any source language implicit ``this`` or ``self`` argument comes first as a
   pointer type.
2. Followed by the function formal arguments in left to right source order.

The source language result arguments are:

1. The function result argument.

The source language input or result struct type arguments that are less than or
equal to 16 bytes, are decomposed recursively into their base type fields, and
each field is passed as if a separate argument. For input arguments, if the
called function requires the struct to be in memory, for example because its
address is taken, then the function body is responsible for allocating a stack
location and copying the field arguments into it. Clang terms this *direct
struct*.

The source language input struct type arguments that are greater than 16 bytes,
are passed by reference. The caller is responsible for allocating a stack
location to make a copy of the struct value and pass the address as the input
argument. The called function is responsible to perform the dereference when
accessing the input argument. Clang terms this *by-value struct*.

A source language result struct type argument that is greater than 16 bytes, is
returned by reference. The caller is responsible for allocating a stack location
to hold the result value and passes the address as the last input argument
(before the implicit input arguments). In this case there are no result
arguments. The called function is responsible to perform the dereference when
storing the result value. Clang terms this *structured return (sret)*.

*TODO: correct the ``sret`` definition.*

.. TODO::

  Is this definition correct? Or is ``sret`` only used if passing in registers, and
  pass as non-decomposed struct as stack argument? Or something else? Is the
  memory location in the caller stack frame, or a stack memory argument and so
  no address is passed as the caller can directly write to the argument stack
  location? But then the stack location is still live after return. If an
  argument stack location is it the first stack argument or the last one?

Lambda argument types are treated as struct types with an implementation defined
set of fields.

.. TODO::

  Need to specify the ABI for lambda types for AMDGPU.

For AMDGPU backend all source language arguments (including the decomposed
struct type arguments) are passed in VGPRs unless marked ``inreg`` in which case
they are passed in SGPRs.

The AMDGPU backend walks the function call graph from the leaves to determine
which implicit input arguments are used, propagating to each caller of the
function. The used implicit arguments are appended to the function arguments
after the source language arguments in the following order:

.. TODO::

  Is recursion or external functions supported?

1.  Work-Item ID (1 VGPR)

    The X, Y and Z work-item ID are packed into a single VGRP with the following
    layout. Only fields actually used by the function are set. The other bits
    are undefined.

    The values come from the initial kernel execution state. See
    :ref:`amdgpu-amdhsa-initial-kernel-execution-state`.

    .. table:: Work-item implicit argument layout
      :name: amdgpu-amdhsa-workitem-implicit-argument-layout-table

      ======= ======= ==============
      Bits    Size    Field Name
      ======= ======= ==============
      9:0     10 bits X Work-Item ID
      19:10   10 bits Y Work-Item ID
      29:20   10 bits Z Work-Item ID
      31:30   2 bits  Unused
      ======= ======= ==============

2.  Dispatch Ptr (2 SGPRs)

    The value comes from the initial kernel execution state. See
    :ref:`amdgpu-amdhsa-sgpr-register-set-up-order-table`.

3.  Queue Ptr (2 SGPRs)

    The value comes from the initial kernel execution state. See
    :ref:`amdgpu-amdhsa-sgpr-register-set-up-order-table`.

4.  Kernarg Segment Ptr (2 SGPRs)

    The value comes from the initial kernel execution state. See
    :ref:`amdgpu-amdhsa-sgpr-register-set-up-order-table`.

5.  Dispatch id (2 SGPRs)

    The value comes from the initial kernel execution state. See
    :ref:`amdgpu-amdhsa-sgpr-register-set-up-order-table`.

6.  Work-Group ID X (1 SGPR)

    The value comes from the initial kernel execution state. See
    :ref:`amdgpu-amdhsa-sgpr-register-set-up-order-table`.

7.  Work-Group ID Y (1 SGPR)

    The value comes from the initial kernel execution state. See
    :ref:`amdgpu-amdhsa-sgpr-register-set-up-order-table`.

8.  Work-Group ID Z (1 SGPR)

    The value comes from the initial kernel execution state. See
    :ref:`amdgpu-amdhsa-sgpr-register-set-up-order-table`.

9.  Implicit Argument Ptr (2 SGPRs)

    The value is computed by adding an offset to Kernarg Segment Ptr to get the
    global address space pointer to the first kernarg implicit argument.

The input and result arguments are assigned in order in the following manner:

.. note::

  There are likely some errors and omissions in the following description that
  need correction.

  .. TODO::

    Check the Clang source code to decipher how function arguments and return
    results are handled. Also see the AMDGPU specific values used.

* VGPR arguments are assigned to consecutive VGPRs starting at VGPR0 up to
  VGPR31.

  If there are more arguments than will fit in these registers, the remaining
  arguments are allocated on the stack in order on naturally aligned
  addresses.

  .. TODO::

    How are overly aligned structures allocated on the stack?

* SGPR arguments are assigned to consecutive SGPRs starting at SGPR0 up to
  SGPR29.

  If there are more arguments than will fit in these registers, the remaining
  arguments are allocated on the stack in order on naturally aligned
  addresses.

Note that decomposed struct type arguments may have some fields passed in
registers and some in memory.

.. TODO::

  So, a struct which can pass some fields as decomposed register arguments, will
  pass the rest as decomposed stack elements? But an argument that will not start
  in registers will not be decomposed and will be passed as a non-decomposed
  stack value?

The following is not part of the AMDGPU function calling convention but
describes how the AMDGPU implements function calls:

1.  SGPR33 is used as a frame pointer (FP) if necessary. Like the SP it is an
    unswizzled scratch address. It is only needed if runtime sized ``alloca``
    are used, or for the reasons defined in ``SIFrameLowering``.
2.  Runtime stack alignment is supported. SGPR34 is used as a base pointer (BP)
    to access the incoming stack arguments in the function. The BP is needed
    only when the function requires the runtime stack alignment.

3.  Allocating SGPR arguments on the stack are not supported.

4.  No CFI is currently generated. See
    :ref:`amdgpu-dwarf-call-frame-information`.

    .. note::

      CFI will be generated that defines the CFA as the unswizzled address
      relative to the wave scratch base in the unswizzled private address space
      of the lowest address stack allocated local variable.

      ``DW_AT_frame_base`` will be defined as the swizzled address in the
      swizzled private address space by dividing the CFA by the wavefront size
      (since CFA is always at least dword aligned which matches the scratch
      swizzle element size).

      If no dynamic stack alignment was performed, the stack allocated arguments
      are accessed as negative offsets relative to ``DW_AT_frame_base``, and the
      local variables and register spill slots are accessed as positive offsets
      relative to ``DW_AT_frame_base``.

5.  Function argument passing is implemented by copying the input physical
    registers to virtual registers on entry. The register allocator can spill if
    necessary. These are copied back to physical registers at call sites. The
    net effect is that each function call can have these values in entirely
    distinct locations. The IPRA can help avoid shuffling argument registers.
6.  Call sites are implemented by setting up the arguments at positive offsets
    from SP. Then SP is incremented to account for the known frame size before
    the call and decremented after the call.

    .. note::

      The CFI will reflect the changed calculation needed to compute the CFA
      from SP.

7.  4 byte spill slots are used in the stack frame. One slot is allocated for an
    emergency spill slot. Buffer instructions are used for stack accesses and
    not the ``flat_scratch`` instruction.

    .. TODO::

      Explain when the emergency spill slot is used.

.. TODO::

  Possible broken issues:

  - Stack arguments must be aligned to required alignment.
  - Stack is aligned to max(16, max formal argument alignment)
  - Direct argument < 64 bits should check register budget.
  - Register budget calculation should respect ``inreg`` for SGPR.
  - SGPR overflow is not handled.
  - struct with 1 member unpeeling is not checking size of member.
  - ``sret`` is after ``this`` pointer.
  - Caller is not implementing stack realignment: need an extra pointer.
  - Should say AMDGPU passes FP rather than SP.
  - Should CFI define CFA as address of locals or arguments. Difference is
    apparent when have implemented dynamic alignment.
  - If ``SCRATCH`` instruction could allow negative offsets, then can make FP be
    highest address of stack frame and use negative offset for locals. Would
    allow SP to be the same as FP and could support signal-handler-like as now
    have a real SP for the top of the stack.
  - How is ``sret`` passed on the stack? In argument stack area? Can it overlay
    arguments?
