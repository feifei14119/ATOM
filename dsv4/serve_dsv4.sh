rm -r ~/.cache/atom
MODEL_PATH="${1:-/data/DeepSeek-V4-Flash}"

# --- MLA dump control (atom/model_ops/mla_dump.py) ----------------------------
# Dumps the V4 sparse MLA decode (sparse_attn_v4_paged_decode) inputs/output +
# a params manifest for the aiter pa_decode_sparse unit test. Defaults ON to
# /data/mla_dump; override or disable from the outer env, e.g.:
#   ATOM_DUMP_MLA_DIR=/data/mla_dump ATOM_DUMP_MLA_MAX=16 bash serve_dsv4.sh
#   ATOM_DUMP_MLA_DIR= bash serve_dsv4.sh      # empty disables dumping
DUMP_MLA_DIR="${ATOM_DUMP_MLA_DIR:-/data/mla_dump}"
DUMP_MLA_MAX="${ATOM_DUMP_MLA_MAX:-8}"
DUMP_MLA_LAYERS="${ATOM_DUMP_MLA_LAYERS:-}"

HSA_ENABLE_SDMA=1 \
HSA_USE_SVM=1 \
HSA_XNACK=1 \
AITER_DISABLE_KERNARG_PRELOAD=0 \
ATOM_USE_TRITON_MOE=1 \
ATOM_USE_UNIFIED_ATTN=1 \
ATOM_FORCE_ATTN_TRITON=1 \
ATOM_LOADER_USE_THREADPOOL=0 \
ATOM_USE_UNIFIED_ATTN=1 \
AITER_ROPE_TRITON_BACKEND=1 \
ATOM_ENABLE_DS_QKNORM_FUSION=0 \
ATOM_ENABLE_DS_INPUT_RMSNORM_QUANT_FUSION=0 \
ATOM_ENABLE_DS_QKNORM_QUANT_FUSION=0 \
ATOM_USE_TRITON_GEMM=1 \
ENABLE_DS_QKNORM_FUSION=0 \
ENABLE_CK=0 \
AITER_USE_OPUS_MOE_SORTING=1 \
ATOM_DUMP_MLA_DIR="$DUMP_MLA_DIR" \
ATOM_DUMP_MLA_MAX="$DUMP_MLA_MAX" \
ATOM_DUMP_MLA_LAYERS="$DUMP_MLA_LAYERS" \
python -m atom.entrypoints.openai_server --model "$MODEL_PATH" --kv_cache_dtype fp8 --torch-profiler-dir /app/trace
