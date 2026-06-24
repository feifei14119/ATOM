curl -X POST http://localhost:8000/v1/chat/completions   -H "Content-Type: application/json"   -d '{
    "messages": [{"role": "user", "content": "introduce yourself"}],
    "max_tokens": 128,
    "temperature": 0,
    "stream": false
  }'

