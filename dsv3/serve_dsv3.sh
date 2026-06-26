rm -r ~/.cache/atom
MODEL_PATH="${1:-/data/DeepSeek-V3}"

# --- MLA dump control (atom/model_ops/mla_dump.py) ----------------------------
# Dumps the V3 DENSE MLA decode (aiter.ops.triton.attention.mla_decode.
# decode_attention_fwd) inputs/output + a params manifest for the aiter
# mla_decode_fwd unit test (op_tests/test_mla_v3_atom_dump.py). The dump fires
# only on the triton decode path, so ATOM_USE_TRITON_MLA=1 is required below.
# Defaults ON to /data/mla_dump; override or disable from the outer env, e.g.:
#   ATOM_DUMP_MLA_DIR=/data/mla_dump ATOM_DUMP_MLA_MAX=16 bash serve_dsv3.sh
#   ATOM_DUMP_MLA_DIR= bash serve_dsv3.sh      # empty disables dumping
DUMP_MLA_DIR="${ATOM_DUMP_MLA_DIR:-/data/mla_dump}"
DUMP_MLA_MAX="${ATOM_DUMP_MLA_MAX:-8}"
DUMP_MLA_LAYERS="${ATOM_DUMP_MLA_LAYERS:-}"

HSA_ENABLE_SDMA=1 \
HSA_USE_SVM=1 \
HSA_XNACK=1 \
AITER_DISABLE_KERNARG_PRELOAD=0 \
ATOM_USE_TRITON_MOE=1 \
ATOM_USE_UNIFIED_ATTN=1 \
ATOM_USE_TRITON_MLA=1 \
ATOM_LOADER_USE_THREADPOOL=0 \
AITER_ROPE_TRITON_BACKEND=1 \
ATOM_USE_TRITON_GEMM=1 \
ENABLE_CK=0 \
ATOM_DUMP_MLA_DIR="$DUMP_MLA_DIR" \
ATOM_DUMP_MLA_MAX="$DUMP_MLA_MAX" \
ATOM_DUMP_MLA_LAYERS="$DUMP_MLA_LAYERS" \
python -m atom.entrypoints.openai_server --model "$MODEL_PATH" --kv_cache_dtype fp8 --torch-profiler-dir /app/trace
