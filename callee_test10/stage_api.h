#pragma once
#include <hip/hip_runtime.h>
#include "test_types.h"

// Same C++ interface and calculation payload as callee_test00/stage_probe.s.
// The implicit device ABI inputs must be supplied explicitly to inline asm:
// LLVM cannot infer them by looking at .long instruction words.
__device__ __forceinline__ std::uint32_t stage_probe(
    std::uint32_t bias, std::uint32_t* input, Record* record,
    std::uint32_t tx, std::uint32_t ty, std::uint32_t bx, std::uint32_t by) {
  const auto in = reinterpret_cast<std::uintptr_t>(input);
  const auto out = reinterpret_cast<std::uintptr_t>(record);
  const unsigned packed_tid = threadIdx.x | (threadIdx.y << 10)
                              | (threadIdx.z << 20);
  std::uint32_t result = bias;
  unsigned saved_s105;
  asm volatile(
      // LLVM temporarily reserves s105 for EXEC-copy handling. The raw body
      // still overwrites it; preserve it at this compiler-visible boundary.
      "s_waitcnt_depctr 0\n"
      "s_mov_b32 %[saved], s105\n"
      "s_waitcnt_depctr 0\n"
#include "stage_words.inc"
      "s_mov_b32 s105, %[saved]\n"
      "s_waitcnt_depctr 0\n"
      // v0 is read as the bias and overwritten by the returned result.
      : "+{v0}"(result), [saved] "=&s"(saved_s105)
      : "{v1}"(static_cast<unsigned>(in)),
        "{v2}"(static_cast<unsigned>(in >> 32)),
        "{v3}"(static_cast<unsigned>(out)),
        "{v4}"(static_cast<unsigned>(out >> 32)),
        "{v5}"(tx), "{v6}"(ty), "{v7}"(bx), "{v8}"(by),
        "{v31}"(packed_tid), "{s12}"(blockIdx.x), "{s13}"(blockIdx.y)
      : "v9", "v10", "v11", "v12", "v13", "v14", "v15", "v16", "v17",
        // Net high-register clobbers; s105 is restored by the boundary above.
        "v64", "v65", "v66", "v67", "v68", "v69", "v70", "v71",
        "v72", "v73", "v74", "v75", "v76", "v77", "v78", "v79",
        "v80", "v81", "v82", "v83", "v84", "v85", "v86", "v87",
        "v88", "v89", "v90", "v91", "v92", "v93", "v94", "v95",
        "v96", "v97", "v98", "v99", "v100", "v101", "v102", "v103",
        "v104", "v105", "v106", "v107", "v108", "v109", "v110", "v111",
        "v112", "v113", "v114", "v115", "v116", "v117", "v118", "v119",
        "v120", "v121", "v122", "v123", "v124", "v125", "v126", "v127",
        "v128", "v129", "v130", "v131", "v132", "v133", "v134", "v135",
        "v136", "v137", "v138", "v139", "v140", "v141", "v142", "v143",
        "v144", "v145", "v146", "v147", "v148", "v149", "v150", "v151",
        "v152", "v153", "v154", "v155", "v156", "v157", "v158", "v159",
        "v160", "v161", "v162", "v163", "v164", "v165", "v166", "v167",
        "v168", "v169", "v170", "v171", "v172", "v173", "v174", "v175",
        "v176", "v177", "v178", "v179", "v180", "v181", "v182", "v183",
        "v184", "v185", "v186", "v187", "v188", "v189", "v190", "v191",
        "v192", "v193", "v194", "v195", "v196", "v197", "v198", "v199",
        "v200", "v201", "v202", "v203", "v204", "v205", "v206", "v207",
        "v208", "v209", "v210", "v211", "v212", "v213", "v214", "v215",
        "v216", "v217", "v218", "v219", "v220", "v221", "v222", "v223",
        "v224", "v225", "v226", "v227", "v228", "v229", "v230", "v231",
        "v232", "v233", "v234", "v235", "v236", "v237", "v238", "v239",
        "v240", "v241", "v242", "v243", "v244", "v245", "v246", "v247",
        "v248", "v249", "v250", "v251", "v252", "v253", "v254", "v255",
        "s40", "s41", "s42", "s43", "s44", "s45", "s46", "s47",
        "s48", "s49", "s50", "s51", "s52", "s53", "s54", "s55",
        "s56", "s57", "s58", "s59", "s60", "s61", "s62", "s63",
        "s64", "s65", "s66", "s67", "s68", "s69", "s70", "s71",
        "s72", "s73", "s74", "s75", "s76", "s77", "s78", "s79",
        "s80", "s81", "s82", "s83", "s84", "s85", "s86", "s87",
        "s88", "s89", "s90", "s91", "s92", "s93", "s94", "s95",
        "s96", "s97", "s98", "s99", "s100", "s101", "s102", "s103",
        "s104",
        "s0", "scc", "memory");
  return result;
}
