MODEL_PATH="${1:-/data/DeepSeek-V4-Flash}"
lm_eval --model local-completions \
        --model_args model=${MODEL_PATH},base_url=http://localhost:8000/v1/completions,num_concurrent=65,max_retries=3,max_gen_toks=2048,tokenized_requests=False,trust_remote_code=True \
        --tasks gsm8k \
        --num_fewshot 3 \
	--limit 100
