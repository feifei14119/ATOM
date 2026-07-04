window.BENCHMARK_DATA = {
  "lastUpdate": 1783195034893,
  "repoUrl": "https://github.com/feifei14119/ATOM",
  "entries": {
    "Benchmark": [
      {
        "commit": {
          "author": {
            "name": "junyyang-amd",
            "username": "junyyang-amd",
            "email": "junyyang@amd.com"
          },
          "committer": {
            "name": "GitHub",
            "username": "web-flow",
            "email": "noreply@github.com"
          },
          "id": "4dd63e283e087059e1ea4c4198823b5ef1f40758",
          "message": "[atom-vllm-ci] Move atom vllm CI from mi355 to mi350 (#1323)\n\n* Move gpt-oss and kimi2.5 CI from mi355 to mi350\n\n* Move deepseek-v4-flash and qwen3.5 vllm CI from mi355 to mi350\n\n* Add runner user info\n\n* Add clean up containers function for runner atom-mi35x-8gpu-oot-acc\n\n* CI: tolerate missing Docker config on OOT runners\n\n---------\n\nCo-authored-by: Xin Huang <Xin.Huang@amd.com>",
          "timestamp": "2026-06-24T05:59:22Z",
          "url": "https://github.com/feifei14119/ATOM/commit/4dd63e283e087059e1ea4c4198823b5ef1f40758"
        },
        "date": 1782333005417,
        "tool": "customBiggerIsBetter",
        "benches": [
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc1 request throughput",
            "value": 2288.72,
            "unit": "req/s",
            "extra": "cell=pd-chat-1p1d-conc1 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=411970 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc1 avg latency",
            "value": 0.42,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc1 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=411970 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc1 p99 latency",
            "value": 0.47,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc1 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=411970 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc1 p999 latency",
            "value": 0.6,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc1 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=411970 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc1 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-1p1d-conc1 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=411970 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc16 request throughput",
            "value": 7173.26,
            "unit": "req/s",
            "extra": "cell=pd-chat-1p1d-conc16 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1291187 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc16 avg latency",
            "value": 2.17,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc16 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1291187 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc16 p99 latency",
            "value": 4.7,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc16 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1291187 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc16 p999 latency",
            "value": 6.88,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc16 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1291187 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc16 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-1p1d-conc16 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1291187 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc2 request throughput",
            "value": 3828.6,
            "unit": "req/s",
            "extra": "cell=pd-chat-1p1d-conc2 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=689148 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc2 avg latency",
            "value": 0.5,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc2 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=689148 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc2 p99 latency",
            "value": 0.69,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc2 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=689148 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc2 p999 latency",
            "value": 0.78,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc2 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=689148 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc2 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-1p1d-conc2 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=689148 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc4 request throughput",
            "value": 5591.39,
            "unit": "req/s",
            "extra": "cell=pd-chat-1p1d-conc4 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1006450 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc4 avg latency",
            "value": 0.68,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc4 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1006450 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc4 p99 latency",
            "value": 1.18,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc4 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1006450 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc4 p999 latency",
            "value": 1.97,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc4 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1006450 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc4 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-1p1d-conc4 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1006450 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc8 request throughput",
            "value": 7176.81,
            "unit": "req/s",
            "extra": "cell=pd-chat-1p1d-conc8 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1291825 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc8 avg latency",
            "value": 1.07,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc8 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1291825 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc8 p99 latency",
            "value": 2.08,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc8 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1291825 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc8 p999 latency",
            "value": 3,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc8 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1291825 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc8 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-1p1d-conc8 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1291825 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc1 request throughput",
            "value": 2086.31,
            "unit": "req/s",
            "extra": "cell=pd-chat-2p1d-conc1 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=375535 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc1 avg latency",
            "value": 0.46,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc1 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=375535 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc1 p99 latency",
            "value": 0.79,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc1 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=375535 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc1 p999 latency",
            "value": 2.26,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc1 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=375535 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc1 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-2p1d-conc1 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=375535 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc16 request throughput",
            "value": 8604.69,
            "unit": "req/s",
            "extra": "cell=pd-chat-2p1d-conc16 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1548845 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc16 avg latency",
            "value": 1.81,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc16 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1548845 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc16 p99 latency",
            "value": 3.39,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc16 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1548845 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc16 p999 latency",
            "value": 4.31,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc16 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1548845 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc16 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-2p1d-conc16 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1548845 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc2 request throughput",
            "value": 3795.53,
            "unit": "req/s",
            "extra": "cell=pd-chat-2p1d-conc2 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=683195 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc2 avg latency",
            "value": 0.5,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc2 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=683195 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc2 p99 latency",
            "value": 0.7,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc2 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=683195 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc2 p999 latency",
            "value": 0.79,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc2 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=683195 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc2 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-2p1d-conc2 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=683195 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc4 request throughput",
            "value": 5805.17,
            "unit": "req/s",
            "extra": "cell=pd-chat-2p1d-conc4 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1044930 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc4 avg latency",
            "value": 0.66,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc4 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1044930 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc4 p99 latency",
            "value": 1.09,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc4 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1044930 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc4 p999 latency",
            "value": 1.38,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc4 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1044930 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc4 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-2p1d-conc4 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1044930 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc8 request throughput",
            "value": 7500.29,
            "unit": "req/s",
            "extra": "cell=pd-chat-2p1d-conc8 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1350052 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc8 avg latency",
            "value": 1.03,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc8 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1350052 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc8 p99 latency",
            "value": 1.89,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc8 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1350052 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc8 p999 latency",
            "value": 2.39,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc8 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1350052 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc8 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-2p1d-conc8 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1350052 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc1 request throughput",
            "value": 2243.34,
            "unit": "req/s",
            "extra": "cell=pd-chat-3p1d-conc1 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=403802 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc1 avg latency",
            "value": 0.43,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc1 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=403802 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc1 p99 latency",
            "value": 0.47,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc1 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=403802 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc1 p999 latency",
            "value": 0.62,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc1 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=403802 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc1 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-3p1d-conc1 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=403802 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc16 request throughput",
            "value": 8406.92,
            "unit": "req/s",
            "extra": "cell=pd-chat-3p1d-conc16 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1513245 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc16 avg latency",
            "value": 1.85,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc16 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1513245 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc16 p99 latency",
            "value": 3.53,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc16 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1513245 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc16 p999 latency",
            "value": 4.57,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc16 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1513245 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc16 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-3p1d-conc16 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1513245 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc2 request throughput",
            "value": 3747.03,
            "unit": "req/s",
            "extra": "cell=pd-chat-3p1d-conc2 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=674466 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc2 avg latency",
            "value": 0.51,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc2 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=674466 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc2 p99 latency",
            "value": 0.7,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc2 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=674466 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc2 p999 latency",
            "value": 0.83,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc2 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=674466 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc2 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-3p1d-conc2 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=674466 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc4 request throughput",
            "value": 5672.53,
            "unit": "req/s",
            "extra": "cell=pd-chat-3p1d-conc4 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1021056 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc4 avg latency",
            "value": 0.67,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc4 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1021056 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc4 p99 latency",
            "value": 1.13,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc4 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1021056 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc4 p999 latency",
            "value": 1.5,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc4 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1021056 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc4 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-3p1d-conc4 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1021056 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc8 request throughput",
            "value": 7283.74,
            "unit": "req/s",
            "extra": "cell=pd-chat-3p1d-conc8 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1311074 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc8 avg latency",
            "value": 1.06,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc8 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1311074 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc8 p99 latency",
            "value": 1.95,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc8 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1311074 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc8 p999 latency",
            "value": 2.48,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc8 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1311074 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc8 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-3p1d-conc8 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1311074 Run: https://github.com/feifei14119/ATOM/actions/runs/28124281608"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "name": "Pleaplusone",
            "username": "ganyi1996ppo",
            "email": "ygan@amd.com"
          },
          "committer": {
            "name": "GitHub",
            "username": "web-flow",
            "email": "noreply@github.com"
          },
          "id": "03a3538243e83fe890d80c7ba2a1a73bc796c00e",
          "message": "[MiniMax-M3] gluon pa with shuffle layout for minimax m3  (#1334)\n\n* docs: revise M3 fp8/gluon port plan for first-class framework compat\n\nReplace the env-gated bolt-on approach with one driven by main's existing\nattention-framework contracts: fp8 selected by config.kv_cache_dtype,\nscales returned via KVCacheTensor, binding through build_kv_cache_tensor/\nbind_kv_cache, insert via the quantized hook, metadata via make_sparse_*\nfactories, frozen custom-op signature, CUDAGraph-safe scratch, byte\naccounting. Adds a 9-point contract checklist mapped to each task.\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n\n* feat(attn): SparseMHAPagedAttentionImpl skeleton + Attention impl_cls override\n\nTask 0 of the MiniMax-M3 fp8 KV cache + gluon PA port. Adds the subclass\nscaffold (SparseMHAPagedAttentionImpl extends PagedAttentionImpl, overriding\nonly rope_cache + dispatch_backend via delegation for now) and an optional\nimpl_cls kwarg on Attention.__init__ so a model can plug in a specialized impl\nwhile reusing the backend's metadata builder. Indexer state lives on the impl.\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n\n* feat(minimax_m3): page-16 constants + fused SHUFFLE KV-insert kernel\n\nTask 1 of the M3 fp8/gluon port. Adds ASM_PAGE_SIZE=16 / PAGES_PER_SPARSE_BLOCK=8\nand grafts the Triton fused Gemma-RMSNorm + partial-NeoX-RoPE + page-16 SHUFFLE\nKV-insert kernel (+ host wrapper) from origin/ganyi/shuffle_kv_cache_fp8_eagle.\nGPU round-trip test validates q_out/index_q_out vs PyTorch ref and K/V/index\ncache scatter at each token slot.\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n\n* feat(minimax_m3): page-16 sparse block-table builders + fused topk EMIT_SPARSE_BT\n\nTask 2 of the M3 fp8/gluon port. Grafts the decode + prefill page-16 sparse\nblock-table builders into sparse_attn.py (each selected logical 128-block expands\nto 8 contiguous physical 16-pages, partial tail packed last, exact context_lens),\nand replaces index_topk.py wholesale with the source-branch version that adds the\nfused EMIT_SPARSE_BT block-table emission and MAX_Q spec-decode causal support\n(both opt-in via defaulted kwargs, so existing decode callers are unaffected).\n\nTests: x8 expansion + tail-last packing + ctx lengths for the standalone builder;\nfused EMIT path matches the standalone builder bit-for-bit (num_kv_heads==1).\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n\n* feat(minimax_m3): gluon PA decode + prefill runners over page-16 SHUFFLE cache\n\nTask 3 of the M3 fp8/gluon port. Grafts minimax_m3_sparse_attn_decode_asm,\nminimax_m3_sparse_attn_prefill_asm, and the shared _run_prefill_fp8_gluon helper\nfrom the source branch: index top-k -> page-16 sparse block table -> AITER gluon\nsplit-KV paged-attention (run_pa_decode_gluon), with fp8 vs bf16 compute_type and\nper-token scales selected by the KV cache dtype. Adds `import aiter` (used for\naiter.dtypes.fp8). Parity test (gluon vs Triton split-K decode reference) for\ngqa 8/16; validated further by the existing asm/fp8/prefill oracle tests.\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n\n* feat(attn): implement SparseMHAPagedAttentionImpl.rope_cache override\n\nTask 4 of the M3 fp8/gluon port. The override runs MiniMax-M3's fused\nqk-norm + partial-NeoX-RoPE + page-16 SHUFFLE KV insert + indexer-key insert via\naiter.fused_qknorm_idxrqknorm (consuming the packed qkv), reading the SHUFFLE\nK/V + scale + index caches off the bound layer. It returns the parent's 7-tuple\n(query rotated) and stashes the rotated indexer query on self._index_q for\ndispatch_backend. fp8 vs bf16 selected by kv_cache_dtype; fp8 writes per-token\ndequant scales into k_scale/v_scale. Adds the _minimax_m3_cos_sin_cache helper.\n\nTest (bf16 + fp8): override returns the 7-tuple, populates _index_q with correct\nshape, and mutates the KV/index caches (+ fp8 scales).\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n\n* feat(attn): implement SparseMHAPagedAttentionImpl.dispatch_backend override\n\nTask 5 of the M3 fp8/gluon port. dispatch_backend returns the M3 sparse\nprefill/decode backend callable (parent contract\nfn(q,k,v,k_cache,v_cache,k_scale,v_scale,fwd_ctx)). Both paths select per-token\ntop-k index blocks with the fused page-16 sparse block-table emit, then run the\ngluon split-KV paged-attention over the SHUFFLE cache; fp8 vs bf16 follows the\ncache dtype inside the runners. Prefill uses the sync-free on-device metadata\nfallback (query_req_id/abs_pos/qo_indptr=None). Consumes self._index_q from\nrope_cache and clears it afterward.\n\nNote: index_cache is page-128 3D [num_logical, 128, idx_head_dim], indexed by the\nlogical block_table in index-topk (distinct from the page-16 SHUFFLE KV cache).\nTest (bf16+fp8): dispatch returns the decode callable; running it yields finite\n[tokens, nh, hd] output and clears _index_q.\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n\n* first version of refactor\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* remove unnecessary files\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* runable and can response resonable output\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* acc right\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* reuse mha's allocation for main cache,  view at use time\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* remove prepare mtp metadata\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* format\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* format\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* resolve comments\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n---------\n\nSigned-off-by: ganyi <ygan@amd.com>\nCo-authored-by: Claude <noreply@anthropic.com>",
          "timestamp": "2026-06-25T02:16:58Z",
          "url": "https://github.com/feifei14119/ATOM/commit/03a3538243e83fe890d80c7ba2a1a73bc796c00e"
        },
        "date": 1782420132440,
        "tool": "customBiggerIsBetter",
        "benches": [
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc1 request throughput",
            "value": 2301.8,
            "unit": "req/s",
            "extra": "cell=pd-chat-1p1d-conc1 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=414324 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc1 avg latency",
            "value": 0.41,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc1 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=414324 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc1 p99 latency",
            "value": 0.46,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc1 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=414324 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc1 p999 latency",
            "value": 0.71,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc1 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=414324 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc1 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-1p1d-conc1 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=414324 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc16 request throughput",
            "value": 8733.55,
            "unit": "req/s",
            "extra": "cell=pd-chat-1p1d-conc16 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1572039 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc16 avg latency",
            "value": 1.79,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc16 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1572039 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc16 p99 latency",
            "value": 3.34,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc16 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1572039 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc16 p999 latency",
            "value": 4.25,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc16 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1572039 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc16 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-1p1d-conc16 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1572039 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc2 request throughput",
            "value": 3813.35,
            "unit": "req/s",
            "extra": "cell=pd-chat-1p1d-conc2 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=686403 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc2 avg latency",
            "value": 0.5,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc2 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=686403 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc2 p99 latency",
            "value": 0.69,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc2 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=686403 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc2 p999 latency",
            "value": 0.81,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc2 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=686403 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc2 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-1p1d-conc2 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=686403 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc4 request throughput",
            "value": 5761.98,
            "unit": "req/s",
            "extra": "cell=pd-chat-1p1d-conc4 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1037157 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc4 avg latency",
            "value": 0.66,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc4 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1037157 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc4 p99 latency",
            "value": 1.11,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc4 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1037157 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc4 p999 latency",
            "value": 1.46,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc4 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1037157 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc4 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-1p1d-conc4 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1037157 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc8 request throughput",
            "value": 7485.46,
            "unit": "req/s",
            "extra": "cell=pd-chat-1p1d-conc8 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1347383 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc8 avg latency",
            "value": 1.03,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc8 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1347383 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc8 p99 latency",
            "value": 1.92,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc8 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1347383 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc8 p999 latency",
            "value": 2.45,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc8 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1347383 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc8 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-1p1d-conc8 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1347383 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc1 request throughput",
            "value": 2304.48,
            "unit": "req/s",
            "extra": "cell=pd-chat-2p1d-conc1 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=414806 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc1 avg latency",
            "value": 0.41,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc1 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=414806 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc1 p99 latency",
            "value": 0.46,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc1 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=414806 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc1 p999 latency",
            "value": 0.66,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc1 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=414806 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc1 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-2p1d-conc1 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=414806 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc16 request throughput",
            "value": 8669.67,
            "unit": "req/s",
            "extra": "cell=pd-chat-2p1d-conc16 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1560540 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc16 avg latency",
            "value": 1.8,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc16 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1560540 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc16 p99 latency",
            "value": 3.36,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc16 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1560540 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc16 p999 latency",
            "value": 4.29,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc16 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1560540 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc16 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-2p1d-conc16 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1560540 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc2 request throughput",
            "value": 3813.36,
            "unit": "req/s",
            "extra": "cell=pd-chat-2p1d-conc2 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=686405 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc2 avg latency",
            "value": 0.5,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc2 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=686405 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc2 p99 latency",
            "value": 0.69,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc2 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=686405 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc2 p999 latency",
            "value": 0.8,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc2 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=686405 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc2 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-2p1d-conc2 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=686405 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc4 request throughput",
            "value": 5796.63,
            "unit": "req/s",
            "extra": "cell=pd-chat-2p1d-conc4 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1043394 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc4 avg latency",
            "value": 0.66,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc4 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1043394 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc4 p99 latency",
            "value": 1.1,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc4 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1043394 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc4 p999 latency",
            "value": 1.43,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc4 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1043394 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc4 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-2p1d-conc4 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1043394 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc8 request throughput",
            "value": 7507.63,
            "unit": "req/s",
            "extra": "cell=pd-chat-2p1d-conc8 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1351373 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc8 avg latency",
            "value": 1.03,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc8 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1351373 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc8 p99 latency",
            "value": 1.89,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc8 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1351373 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc8 p999 latency",
            "value": 2.38,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc8 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1351373 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc8 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-2p1d-conc8 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1351373 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc1 request throughput",
            "value": 2302.28,
            "unit": "req/s",
            "extra": "cell=pd-chat-3p1d-conc1 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=414410 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc1 avg latency",
            "value": 0.41,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc1 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=414410 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc1 p99 latency",
            "value": 0.46,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc1 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=414410 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc1 p999 latency",
            "value": 0.56,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc1 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=414410 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc1 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-3p1d-conc1 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=414410 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc16 request throughput",
            "value": 8642.38,
            "unit": "req/s",
            "extra": "cell=pd-chat-3p1d-conc16 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1555628 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc16 avg latency",
            "value": 1.8,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc16 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1555628 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc16 p99 latency",
            "value": 3.39,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc16 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1555628 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc16 p999 latency",
            "value": 4.3,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc16 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1555628 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc16 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-3p1d-conc16 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1555628 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc2 request throughput",
            "value": 3825.25,
            "unit": "req/s",
            "extra": "cell=pd-chat-3p1d-conc2 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=688545 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc2 avg latency",
            "value": 0.5,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc2 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=688545 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc2 p99 latency",
            "value": 0.69,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc2 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=688545 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc2 p999 latency",
            "value": 0.79,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc2 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=688545 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc2 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-3p1d-conc2 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=688545 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc4 request throughput",
            "value": 5802.81,
            "unit": "req/s",
            "extra": "cell=pd-chat-3p1d-conc4 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1044506 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc4 avg latency",
            "value": 0.66,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc4 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1044506 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc4 p99 latency",
            "value": 1.09,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc4 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1044506 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc4 p999 latency",
            "value": 1.42,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc4 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1044506 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc4 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-3p1d-conc4 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1044506 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc8 request throughput",
            "value": 7484.3,
            "unit": "req/s",
            "extra": "cell=pd-chat-3p1d-conc8 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1347174 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc8 avg latency",
            "value": 1.03,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc8 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1347174 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc8 p99 latency",
            "value": 1.9,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc8 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1347174 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc8 p999 latency",
            "value": 2.43,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc8 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1347174 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc8 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-3p1d-conc8 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1347174 Run: https://github.com/feifei14119/ATOM/actions/runs/28196234062"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "name": "Pleaplusone",
            "username": "ganyi1996ppo",
            "email": "ygan@amd.com"
          },
          "committer": {
            "name": "GitHub",
            "username": "web-flow",
            "email": "noreply@github.com"
          },
          "id": "03a3538243e83fe890d80c7ba2a1a73bc796c00e",
          "message": "[MiniMax-M3] gluon pa with shuffle layout for minimax m3  (#1334)\n\n* docs: revise M3 fp8/gluon port plan for first-class framework compat\n\nReplace the env-gated bolt-on approach with one driven by main's existing\nattention-framework contracts: fp8 selected by config.kv_cache_dtype,\nscales returned via KVCacheTensor, binding through build_kv_cache_tensor/\nbind_kv_cache, insert via the quantized hook, metadata via make_sparse_*\nfactories, frozen custom-op signature, CUDAGraph-safe scratch, byte\naccounting. Adds a 9-point contract checklist mapped to each task.\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n\n* feat(attn): SparseMHAPagedAttentionImpl skeleton + Attention impl_cls override\n\nTask 0 of the MiniMax-M3 fp8 KV cache + gluon PA port. Adds the subclass\nscaffold (SparseMHAPagedAttentionImpl extends PagedAttentionImpl, overriding\nonly rope_cache + dispatch_backend via delegation for now) and an optional\nimpl_cls kwarg on Attention.__init__ so a model can plug in a specialized impl\nwhile reusing the backend's metadata builder. Indexer state lives on the impl.\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n\n* feat(minimax_m3): page-16 constants + fused SHUFFLE KV-insert kernel\n\nTask 1 of the M3 fp8/gluon port. Adds ASM_PAGE_SIZE=16 / PAGES_PER_SPARSE_BLOCK=8\nand grafts the Triton fused Gemma-RMSNorm + partial-NeoX-RoPE + page-16 SHUFFLE\nKV-insert kernel (+ host wrapper) from origin/ganyi/shuffle_kv_cache_fp8_eagle.\nGPU round-trip test validates q_out/index_q_out vs PyTorch ref and K/V/index\ncache scatter at each token slot.\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n\n* feat(minimax_m3): page-16 sparse block-table builders + fused topk EMIT_SPARSE_BT\n\nTask 2 of the M3 fp8/gluon port. Grafts the decode + prefill page-16 sparse\nblock-table builders into sparse_attn.py (each selected logical 128-block expands\nto 8 contiguous physical 16-pages, partial tail packed last, exact context_lens),\nand replaces index_topk.py wholesale with the source-branch version that adds the\nfused EMIT_SPARSE_BT block-table emission and MAX_Q spec-decode causal support\n(both opt-in via defaulted kwargs, so existing decode callers are unaffected).\n\nTests: x8 expansion + tail-last packing + ctx lengths for the standalone builder;\nfused EMIT path matches the standalone builder bit-for-bit (num_kv_heads==1).\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n\n* feat(minimax_m3): gluon PA decode + prefill runners over page-16 SHUFFLE cache\n\nTask 3 of the M3 fp8/gluon port. Grafts minimax_m3_sparse_attn_decode_asm,\nminimax_m3_sparse_attn_prefill_asm, and the shared _run_prefill_fp8_gluon helper\nfrom the source branch: index top-k -> page-16 sparse block table -> AITER gluon\nsplit-KV paged-attention (run_pa_decode_gluon), with fp8 vs bf16 compute_type and\nper-token scales selected by the KV cache dtype. Adds `import aiter` (used for\naiter.dtypes.fp8). Parity test (gluon vs Triton split-K decode reference) for\ngqa 8/16; validated further by the existing asm/fp8/prefill oracle tests.\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n\n* feat(attn): implement SparseMHAPagedAttentionImpl.rope_cache override\n\nTask 4 of the M3 fp8/gluon port. The override runs MiniMax-M3's fused\nqk-norm + partial-NeoX-RoPE + page-16 SHUFFLE KV insert + indexer-key insert via\naiter.fused_qknorm_idxrqknorm (consuming the packed qkv), reading the SHUFFLE\nK/V + scale + index caches off the bound layer. It returns the parent's 7-tuple\n(query rotated) and stashes the rotated indexer query on self._index_q for\ndispatch_backend. fp8 vs bf16 selected by kv_cache_dtype; fp8 writes per-token\ndequant scales into k_scale/v_scale. Adds the _minimax_m3_cos_sin_cache helper.\n\nTest (bf16 + fp8): override returns the 7-tuple, populates _index_q with correct\nshape, and mutates the KV/index caches (+ fp8 scales).\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n\n* feat(attn): implement SparseMHAPagedAttentionImpl.dispatch_backend override\n\nTask 5 of the M3 fp8/gluon port. dispatch_backend returns the M3 sparse\nprefill/decode backend callable (parent contract\nfn(q,k,v,k_cache,v_cache,k_scale,v_scale,fwd_ctx)). Both paths select per-token\ntop-k index blocks with the fused page-16 sparse block-table emit, then run the\ngluon split-KV paged-attention over the SHUFFLE cache; fp8 vs bf16 follows the\ncache dtype inside the runners. Prefill uses the sync-free on-device metadata\nfallback (query_req_id/abs_pos/qo_indptr=None). Consumes self._index_q from\nrope_cache and clears it afterward.\n\nNote: index_cache is page-128 3D [num_logical, 128, idx_head_dim], indexed by the\nlogical block_table in index-topk (distinct from the page-16 SHUFFLE KV cache).\nTest (bf16+fp8): dispatch returns the decode callable; running it yields finite\n[tokens, nh, hd] output and clears _index_q.\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n\n* first version of refactor\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* remove unnecessary files\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* runable and can response resonable output\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* acc right\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* reuse mha's allocation for main cache,  view at use time\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* remove prepare mtp metadata\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* format\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* format\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* resolve comments\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n---------\n\nSigned-off-by: ganyi <ygan@amd.com>\nCo-authored-by: Claude <noreply@anthropic.com>",
          "timestamp": "2026-06-25T02:16:58Z",
          "url": "https://github.com/feifei14119/ATOM/commit/03a3538243e83fe890d80c7ba2a1a73bc796c00e"
        },
        "date": 1782505513766,
        "tool": "customBiggerIsBetter",
        "benches": [
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc1 request throughput",
            "value": 2241.48,
            "unit": "req/s",
            "extra": "cell=pd-chat-1p1d-conc1 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=403466 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc1 avg latency",
            "value": 0.43,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc1 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=403466 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc1 p99 latency",
            "value": 0.49,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc1 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=403466 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc1 p999 latency",
            "value": 0.77,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc1 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=403466 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc1 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-1p1d-conc1 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=403466 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc16 request throughput",
            "value": 8257.75,
            "unit": "req/s",
            "extra": "cell=pd-chat-1p1d-conc16 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1486395 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc16 avg latency",
            "value": 1.89,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc16 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1486395 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc16 p99 latency",
            "value": 3.6,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc16 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1486395 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc16 p999 latency",
            "value": 4.64,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc16 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1486395 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc16 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-1p1d-conc16 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1486395 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc2 request throughput",
            "value": 3688.72,
            "unit": "req/s",
            "extra": "cell=pd-chat-1p1d-conc2 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=663969 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc2 avg latency",
            "value": 0.52,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc2 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=663969 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc2 p99 latency",
            "value": 0.75,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc2 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=663969 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc2 p999 latency",
            "value": 0.99,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc2 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=663969 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc2 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-1p1d-conc2 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=663969 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc4 request throughput",
            "value": 5585.7,
            "unit": "req/s",
            "extra": "cell=pd-chat-1p1d-conc4 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1005426 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc4 avg latency",
            "value": 0.68,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc4 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1005426 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc4 p99 latency",
            "value": 1.16,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc4 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1005426 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc4 p999 latency",
            "value": 1.54,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc4 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1005426 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc4 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-1p1d-conc4 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1005426 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc8 request throughput",
            "value": 7248.94,
            "unit": "req/s",
            "extra": "cell=pd-chat-1p1d-conc8 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1304810 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc8 avg latency",
            "value": 1.06,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc8 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1304810 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc8 p99 latency",
            "value": 1.98,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc8 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1304810 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc8 p999 latency",
            "value": 2.53,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc8 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1304810 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc8 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-1p1d-conc8 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1304810 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc1 request throughput",
            "value": 2219.22,
            "unit": "req/s",
            "extra": "cell=pd-chat-2p1d-conc1 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=399459 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc1 avg latency",
            "value": 0.43,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc1 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=399459 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc1 p99 latency",
            "value": 0.59,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc1 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=399459 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc1 p999 latency",
            "value": 0.81,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc1 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=399459 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc1 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-2p1d-conc1 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=399459 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc16 request throughput",
            "value": 8384.19,
            "unit": "req/s",
            "extra": "cell=pd-chat-2p1d-conc16 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1509155 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc16 avg latency",
            "value": 1.86,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc16 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1509155 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc16 p99 latency",
            "value": 3.52,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc16 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1509155 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc16 p999 latency",
            "value": 4.51,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc16 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1509155 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc16 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-2p1d-conc16 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1509155 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc2 request throughput",
            "value": 3638.78,
            "unit": "req/s",
            "extra": "cell=pd-chat-2p1d-conc2 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=654980 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc2 avg latency",
            "value": 0.52,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc2 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=654980 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc2 p99 latency",
            "value": 0.76,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc2 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=654980 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc2 p999 latency",
            "value": 1.02,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc2 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=654980 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc2 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-2p1d-conc2 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=654980 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc4 request throughput",
            "value": 5450.86,
            "unit": "req/s",
            "extra": "cell=pd-chat-2p1d-conc4 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=981154 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc4 avg latency",
            "value": 0.7,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc4 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=981154 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc4 p99 latency",
            "value": 1.19,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc4 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=981154 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc4 p999 latency",
            "value": 1.58,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc4 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=981154 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc4 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-2p1d-conc4 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=981154 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc8 request throughput",
            "value": 7090.37,
            "unit": "req/s",
            "extra": "cell=pd-chat-2p1d-conc8 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1276266 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc8 avg latency",
            "value": 1.09,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc8 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1276266 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc8 p99 latency",
            "value": 2.06,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc8 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1276266 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc8 p999 latency",
            "value": 2.68,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc8 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1276266 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc8 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-2p1d-conc8 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1276266 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc1 request throughput",
            "value": 2225.43,
            "unit": "req/s",
            "extra": "cell=pd-chat-3p1d-conc1 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=400577 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc1 avg latency",
            "value": 0.43,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc1 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=400577 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc1 p99 latency",
            "value": 0.49,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc1 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=400577 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc1 p999 latency",
            "value": 0.8,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc1 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=400577 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc1 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-3p1d-conc1 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=400577 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc16 request throughput",
            "value": 8377.86,
            "unit": "req/s",
            "extra": "cell=pd-chat-3p1d-conc16 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1508015 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc16 avg latency",
            "value": 1.86,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc16 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1508015 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc16 p99 latency",
            "value": 3.52,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc16 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1508015 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc16 p999 latency",
            "value": 4.5,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc16 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1508015 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc16 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-3p1d-conc16 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1508015 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc2 request throughput",
            "value": 3671.29,
            "unit": "req/s",
            "extra": "cell=pd-chat-3p1d-conc2 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=660833 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc2 avg latency",
            "value": 0.52,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc2 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=660833 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc2 p99 latency",
            "value": 0.72,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc2 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=660833 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc2 p999 latency",
            "value": 0.89,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc2 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=660833 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc2 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-3p1d-conc2 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=660833 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc4 request throughput",
            "value": 5578.37,
            "unit": "req/s",
            "extra": "cell=pd-chat-3p1d-conc4 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1004107 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc4 avg latency",
            "value": 0.68,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc4 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1004107 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc4 p99 latency",
            "value": 1.14,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc4 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1004107 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc4 p999 latency",
            "value": 1.46,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc4 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1004107 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc4 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-3p1d-conc4 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1004107 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc8 request throughput",
            "value": 7189.85,
            "unit": "req/s",
            "extra": "cell=pd-chat-3p1d-conc8 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1294173 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc8 avg latency",
            "value": 1.07,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc8 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1294173 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc8 p99 latency",
            "value": 2.01,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc8 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1294173 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc8 p999 latency",
            "value": 2.6,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc8 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1294173 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc8 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-3p1d-conc8 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1294173 Run: https://github.com/feifei14119/ATOM/actions/runs/28260581116"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "name": "Pleaplusone",
            "username": "ganyi1996ppo",
            "email": "ygan@amd.com"
          },
          "committer": {
            "name": "GitHub",
            "username": "web-flow",
            "email": "noreply@github.com"
          },
          "id": "03a3538243e83fe890d80c7ba2a1a73bc796c00e",
          "message": "[MiniMax-M3] gluon pa with shuffle layout for minimax m3  (#1334)\n\n* docs: revise M3 fp8/gluon port plan for first-class framework compat\n\nReplace the env-gated bolt-on approach with one driven by main's existing\nattention-framework contracts: fp8 selected by config.kv_cache_dtype,\nscales returned via KVCacheTensor, binding through build_kv_cache_tensor/\nbind_kv_cache, insert via the quantized hook, metadata via make_sparse_*\nfactories, frozen custom-op signature, CUDAGraph-safe scratch, byte\naccounting. Adds a 9-point contract checklist mapped to each task.\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n\n* feat(attn): SparseMHAPagedAttentionImpl skeleton + Attention impl_cls override\n\nTask 0 of the MiniMax-M3 fp8 KV cache + gluon PA port. Adds the subclass\nscaffold (SparseMHAPagedAttentionImpl extends PagedAttentionImpl, overriding\nonly rope_cache + dispatch_backend via delegation for now) and an optional\nimpl_cls kwarg on Attention.__init__ so a model can plug in a specialized impl\nwhile reusing the backend's metadata builder. Indexer state lives on the impl.\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n\n* feat(minimax_m3): page-16 constants + fused SHUFFLE KV-insert kernel\n\nTask 1 of the M3 fp8/gluon port. Adds ASM_PAGE_SIZE=16 / PAGES_PER_SPARSE_BLOCK=8\nand grafts the Triton fused Gemma-RMSNorm + partial-NeoX-RoPE + page-16 SHUFFLE\nKV-insert kernel (+ host wrapper) from origin/ganyi/shuffle_kv_cache_fp8_eagle.\nGPU round-trip test validates q_out/index_q_out vs PyTorch ref and K/V/index\ncache scatter at each token slot.\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n\n* feat(minimax_m3): page-16 sparse block-table builders + fused topk EMIT_SPARSE_BT\n\nTask 2 of the M3 fp8/gluon port. Grafts the decode + prefill page-16 sparse\nblock-table builders into sparse_attn.py (each selected logical 128-block expands\nto 8 contiguous physical 16-pages, partial tail packed last, exact context_lens),\nand replaces index_topk.py wholesale with the source-branch version that adds the\nfused EMIT_SPARSE_BT block-table emission and MAX_Q spec-decode causal support\n(both opt-in via defaulted kwargs, so existing decode callers are unaffected).\n\nTests: x8 expansion + tail-last packing + ctx lengths for the standalone builder;\nfused EMIT path matches the standalone builder bit-for-bit (num_kv_heads==1).\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n\n* feat(minimax_m3): gluon PA decode + prefill runners over page-16 SHUFFLE cache\n\nTask 3 of the M3 fp8/gluon port. Grafts minimax_m3_sparse_attn_decode_asm,\nminimax_m3_sparse_attn_prefill_asm, and the shared _run_prefill_fp8_gluon helper\nfrom the source branch: index top-k -> page-16 sparse block table -> AITER gluon\nsplit-KV paged-attention (run_pa_decode_gluon), with fp8 vs bf16 compute_type and\nper-token scales selected by the KV cache dtype. Adds `import aiter` (used for\naiter.dtypes.fp8). Parity test (gluon vs Triton split-K decode reference) for\ngqa 8/16; validated further by the existing asm/fp8/prefill oracle tests.\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n\n* feat(attn): implement SparseMHAPagedAttentionImpl.rope_cache override\n\nTask 4 of the M3 fp8/gluon port. The override runs MiniMax-M3's fused\nqk-norm + partial-NeoX-RoPE + page-16 SHUFFLE KV insert + indexer-key insert via\naiter.fused_qknorm_idxrqknorm (consuming the packed qkv), reading the SHUFFLE\nK/V + scale + index caches off the bound layer. It returns the parent's 7-tuple\n(query rotated) and stashes the rotated indexer query on self._index_q for\ndispatch_backend. fp8 vs bf16 selected by kv_cache_dtype; fp8 writes per-token\ndequant scales into k_scale/v_scale. Adds the _minimax_m3_cos_sin_cache helper.\n\nTest (bf16 + fp8): override returns the 7-tuple, populates _index_q with correct\nshape, and mutates the KV/index caches (+ fp8 scales).\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n\n* feat(attn): implement SparseMHAPagedAttentionImpl.dispatch_backend override\n\nTask 5 of the M3 fp8/gluon port. dispatch_backend returns the M3 sparse\nprefill/decode backend callable (parent contract\nfn(q,k,v,k_cache,v_cache,k_scale,v_scale,fwd_ctx)). Both paths select per-token\ntop-k index blocks with the fused page-16 sparse block-table emit, then run the\ngluon split-KV paged-attention over the SHUFFLE cache; fp8 vs bf16 follows the\ncache dtype inside the runners. Prefill uses the sync-free on-device metadata\nfallback (query_req_id/abs_pos/qo_indptr=None). Consumes self._index_q from\nrope_cache and clears it afterward.\n\nNote: index_cache is page-128 3D [num_logical, 128, idx_head_dim], indexed by the\nlogical block_table in index-topk (distinct from the page-16 SHUFFLE KV cache).\nTest (bf16+fp8): dispatch returns the decode callable; running it yields finite\n[tokens, nh, hd] output and clears _index_q.\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n\n* first version of refactor\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* remove unnecessary files\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* runable and can response resonable output\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* acc right\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* reuse mha's allocation for main cache,  view at use time\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* remove prepare mtp metadata\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* format\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* format\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* resolve comments\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n---------\n\nSigned-off-by: ganyi <ygan@amd.com>\nCo-authored-by: Claude <noreply@anthropic.com>",
          "timestamp": "2026-06-25T02:16:58Z",
          "url": "https://github.com/feifei14119/ATOM/commit/03a3538243e83fe890d80c7ba2a1a73bc796c00e"
        },
        "date": 1782590510608,
        "tool": "customBiggerIsBetter",
        "benches": [
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc1 request throughput",
            "value": 2106.53,
            "unit": "req/s",
            "extra": "cell=pd-chat-1p1d-conc1 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=379175 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc1 avg latency",
            "value": 0.46,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc1 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=379175 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc1 p99 latency",
            "value": 0.53,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc1 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=379175 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc1 p999 latency",
            "value": 0.58,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc1 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=379175 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc1 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-1p1d-conc1 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=379175 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc16 request throughput",
            "value": 7457.98,
            "unit": "req/s",
            "extra": "cell=pd-chat-1p1d-conc16 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1342437 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc16 avg latency",
            "value": 2.1,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc16 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1342437 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc16 p99 latency",
            "value": 3.92,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc16 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1342437 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc16 p999 latency",
            "value": 4.99,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc16 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1342437 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc16 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-1p1d-conc16 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1342437 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc2 request throughput",
            "value": 3408.92,
            "unit": "req/s",
            "extra": "cell=pd-chat-1p1d-conc2 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=613605 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc2 avg latency",
            "value": 0.56,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc2 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=613605 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc2 p99 latency",
            "value": 0.77,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc2 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=613605 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc2 p999 latency",
            "value": 0.89,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc2 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=613605 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc2 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-1p1d-conc2 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=613605 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc4 request throughput",
            "value": 5129.77,
            "unit": "req/s",
            "extra": "cell=pd-chat-1p1d-conc4 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=923359 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc4 avg latency",
            "value": 0.75,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc4 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=923359 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc4 p99 latency",
            "value": 1.24,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc4 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=923359 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc4 p999 latency",
            "value": 1.57,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc4 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=923359 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc4 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-1p1d-conc4 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=923359 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc8 request throughput",
            "value": 6465.14,
            "unit": "req/s",
            "extra": "cell=pd-chat-1p1d-conc8 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1163725 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc8 avg latency",
            "value": 1.2,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc8 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1163725 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc8 p99 latency",
            "value": 2.19,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc8 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1163725 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc8 p999 latency",
            "value": 2.77,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc8 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1163725 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc8 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-1p1d-conc8 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1163725 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc1 request throughput",
            "value": 2100.52,
            "unit": "req/s",
            "extra": "cell=pd-chat-2p1d-conc1 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=378093 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc1 avg latency",
            "value": 0.46,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc1 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=378093 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc1 p99 latency",
            "value": 0.52,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc1 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=378093 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc1 p999 latency",
            "value": 0.58,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc1 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=378093 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc1 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-2p1d-conc1 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=378093 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc16 request throughput",
            "value": 7505.89,
            "unit": "req/s",
            "extra": "cell=pd-chat-2p1d-conc16 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1351060 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc16 avg latency",
            "value": 2.08,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc16 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1351060 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc16 p99 latency",
            "value": 3.91,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc16 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1351060 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc16 p999 latency",
            "value": 4.97,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc16 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1351060 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc16 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-2p1d-conc16 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1351060 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc2 request throughput",
            "value": 3421.07,
            "unit": "req/s",
            "extra": "cell=pd-chat-2p1d-conc2 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=615792 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc2 avg latency",
            "value": 0.56,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc2 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=615792 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc2 p99 latency",
            "value": 0.77,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc2 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=615792 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc2 p999 latency",
            "value": 0.89,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc2 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=615792 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc2 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-2p1d-conc2 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=615792 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc4 request throughput",
            "value": 5146.62,
            "unit": "req/s",
            "extra": "cell=pd-chat-2p1d-conc4 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=926391 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc4 avg latency",
            "value": 0.74,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc4 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=926391 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc4 p99 latency",
            "value": 1.24,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc4 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=926391 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc4 p999 latency",
            "value": 1.56,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc4 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=926391 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc4 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-2p1d-conc4 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=926391 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc8 request throughput",
            "value": 6438.47,
            "unit": "req/s",
            "extra": "cell=pd-chat-2p1d-conc8 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1158924 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc8 avg latency",
            "value": 1.2,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc8 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1158924 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc8 p99 latency",
            "value": 2.21,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc8 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1158924 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc8 p999 latency",
            "value": 2.8,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc8 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1158924 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc8 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-2p1d-conc8 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1158924 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc1 request throughput",
            "value": 2119.99,
            "unit": "req/s",
            "extra": "cell=pd-chat-3p1d-conc1 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=381598 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc1 avg latency",
            "value": 0.45,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc1 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=381598 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc1 p99 latency",
            "value": 0.52,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc1 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=381598 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc1 p999 latency",
            "value": 0.57,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc1 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=381598 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc1 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-3p1d-conc1 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=381598 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc16 request throughput",
            "value": 7477.06,
            "unit": "req/s",
            "extra": "cell=pd-chat-3p1d-conc16 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1345871 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc16 avg latency",
            "value": 2.09,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc16 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1345871 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc16 p99 latency",
            "value": 3.92,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc16 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1345871 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc16 p999 latency",
            "value": 4.98,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc16 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1345871 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc16 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-3p1d-conc16 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1345871 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc2 request throughput",
            "value": 3422.94,
            "unit": "req/s",
            "extra": "cell=pd-chat-3p1d-conc2 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=616129 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc2 avg latency",
            "value": 0.56,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc2 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=616129 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc2 p99 latency",
            "value": 0.77,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc2 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=616129 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc2 p999 latency",
            "value": 0.88,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc2 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=616129 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc2 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-3p1d-conc2 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=616129 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc4 request throughput",
            "value": 5187.83,
            "unit": "req/s",
            "extra": "cell=pd-chat-3p1d-conc4 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=933809 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc4 avg latency",
            "value": 0.74,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc4 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=933809 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc4 p99 latency",
            "value": 1.23,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc4 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=933809 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc4 p999 latency",
            "value": 1.55,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc4 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=933809 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc4 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-3p1d-conc4 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=933809 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc8 request throughput",
            "value": 6556.84,
            "unit": "req/s",
            "extra": "cell=pd-chat-3p1d-conc8 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1180232 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc8 avg latency",
            "value": 1.18,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc8 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1180232 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc8 p99 latency",
            "value": 2.17,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc8 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1180232 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc8 p999 latency",
            "value": 2.74,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc8 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1180232 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc8 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-3p1d-conc8 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1180232 Run: https://github.com/feifei14119/ATOM/actions/runs/28298893221"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "name": "Pleaplusone",
            "username": "ganyi1996ppo",
            "email": "ygan@amd.com"
          },
          "committer": {
            "name": "GitHub",
            "username": "web-flow",
            "email": "noreply@github.com"
          },
          "id": "03a3538243e83fe890d80c7ba2a1a73bc796c00e",
          "message": "[MiniMax-M3] gluon pa with shuffle layout for minimax m3  (#1334)\n\n* docs: revise M3 fp8/gluon port plan for first-class framework compat\n\nReplace the env-gated bolt-on approach with one driven by main's existing\nattention-framework contracts: fp8 selected by config.kv_cache_dtype,\nscales returned via KVCacheTensor, binding through build_kv_cache_tensor/\nbind_kv_cache, insert via the quantized hook, metadata via make_sparse_*\nfactories, frozen custom-op signature, CUDAGraph-safe scratch, byte\naccounting. Adds a 9-point contract checklist mapped to each task.\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n\n* feat(attn): SparseMHAPagedAttentionImpl skeleton + Attention impl_cls override\n\nTask 0 of the MiniMax-M3 fp8 KV cache + gluon PA port. Adds the subclass\nscaffold (SparseMHAPagedAttentionImpl extends PagedAttentionImpl, overriding\nonly rope_cache + dispatch_backend via delegation for now) and an optional\nimpl_cls kwarg on Attention.__init__ so a model can plug in a specialized impl\nwhile reusing the backend's metadata builder. Indexer state lives on the impl.\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n\n* feat(minimax_m3): page-16 constants + fused SHUFFLE KV-insert kernel\n\nTask 1 of the M3 fp8/gluon port. Adds ASM_PAGE_SIZE=16 / PAGES_PER_SPARSE_BLOCK=8\nand grafts the Triton fused Gemma-RMSNorm + partial-NeoX-RoPE + page-16 SHUFFLE\nKV-insert kernel (+ host wrapper) from origin/ganyi/shuffle_kv_cache_fp8_eagle.\nGPU round-trip test validates q_out/index_q_out vs PyTorch ref and K/V/index\ncache scatter at each token slot.\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n\n* feat(minimax_m3): page-16 sparse block-table builders + fused topk EMIT_SPARSE_BT\n\nTask 2 of the M3 fp8/gluon port. Grafts the decode + prefill page-16 sparse\nblock-table builders into sparse_attn.py (each selected logical 128-block expands\nto 8 contiguous physical 16-pages, partial tail packed last, exact context_lens),\nand replaces index_topk.py wholesale with the source-branch version that adds the\nfused EMIT_SPARSE_BT block-table emission and MAX_Q spec-decode causal support\n(both opt-in via defaulted kwargs, so existing decode callers are unaffected).\n\nTests: x8 expansion + tail-last packing + ctx lengths for the standalone builder;\nfused EMIT path matches the standalone builder bit-for-bit (num_kv_heads==1).\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n\n* feat(minimax_m3): gluon PA decode + prefill runners over page-16 SHUFFLE cache\n\nTask 3 of the M3 fp8/gluon port. Grafts minimax_m3_sparse_attn_decode_asm,\nminimax_m3_sparse_attn_prefill_asm, and the shared _run_prefill_fp8_gluon helper\nfrom the source branch: index top-k -> page-16 sparse block table -> AITER gluon\nsplit-KV paged-attention (run_pa_decode_gluon), with fp8 vs bf16 compute_type and\nper-token scales selected by the KV cache dtype. Adds `import aiter` (used for\naiter.dtypes.fp8). Parity test (gluon vs Triton split-K decode reference) for\ngqa 8/16; validated further by the existing asm/fp8/prefill oracle tests.\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n\n* feat(attn): implement SparseMHAPagedAttentionImpl.rope_cache override\n\nTask 4 of the M3 fp8/gluon port. The override runs MiniMax-M3's fused\nqk-norm + partial-NeoX-RoPE + page-16 SHUFFLE KV insert + indexer-key insert via\naiter.fused_qknorm_idxrqknorm (consuming the packed qkv), reading the SHUFFLE\nK/V + scale + index caches off the bound layer. It returns the parent's 7-tuple\n(query rotated) and stashes the rotated indexer query on self._index_q for\ndispatch_backend. fp8 vs bf16 selected by kv_cache_dtype; fp8 writes per-token\ndequant scales into k_scale/v_scale. Adds the _minimax_m3_cos_sin_cache helper.\n\nTest (bf16 + fp8): override returns the 7-tuple, populates _index_q with correct\nshape, and mutates the KV/index caches (+ fp8 scales).\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n\n* feat(attn): implement SparseMHAPagedAttentionImpl.dispatch_backend override\n\nTask 5 of the M3 fp8/gluon port. dispatch_backend returns the M3 sparse\nprefill/decode backend callable (parent contract\nfn(q,k,v,k_cache,v_cache,k_scale,v_scale,fwd_ctx)). Both paths select per-token\ntop-k index blocks with the fused page-16 sparse block-table emit, then run the\ngluon split-KV paged-attention over the SHUFFLE cache; fp8 vs bf16 follows the\ncache dtype inside the runners. Prefill uses the sync-free on-device metadata\nfallback (query_req_id/abs_pos/qo_indptr=None). Consumes self._index_q from\nrope_cache and clears it afterward.\n\nNote: index_cache is page-128 3D [num_logical, 128, idx_head_dim], indexed by the\nlogical block_table in index-topk (distinct from the page-16 SHUFFLE KV cache).\nTest (bf16+fp8): dispatch returns the decode callable; running it yields finite\n[tokens, nh, hd] output and clears _index_q.\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n\n* first version of refactor\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* remove unnecessary files\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* runable and can response resonable output\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* acc right\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* reuse mha's allocation for main cache,  view at use time\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* remove prepare mtp metadata\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* format\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* format\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* resolve comments\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n---------\n\nSigned-off-by: ganyi <ygan@amd.com>\nCo-authored-by: Claude <noreply@anthropic.com>",
          "timestamp": "2026-06-25T02:16:58Z",
          "url": "https://github.com/feifei14119/ATOM/commit/03a3538243e83fe890d80c7ba2a1a73bc796c00e"
        },
        "date": 1782676887782,
        "tool": "customBiggerIsBetter",
        "benches": [
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc1 request throughput",
            "value": 2277.07,
            "unit": "req/s",
            "extra": "cell=pd-chat-1p1d-conc1 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=409872 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc1 avg latency",
            "value": 0.42,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc1 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=409872 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc1 p99 latency",
            "value": 0.48,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc1 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=409872 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc1 p999 latency",
            "value": 0.53,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc1 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=409872 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc1 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-1p1d-conc1 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=409872 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc16 request throughput",
            "value": 7762.52,
            "unit": "req/s",
            "extra": "cell=pd-chat-1p1d-conc16 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1397253 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc16 avg latency",
            "value": 2.02,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc16 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1397253 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc16 p99 latency",
            "value": 3.77,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc16 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1397253 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc16 p999 latency",
            "value": 4.8,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc16 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1397253 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc16 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-1p1d-conc16 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1397253 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc2 request throughput",
            "value": 3661.81,
            "unit": "req/s",
            "extra": "cell=pd-chat-1p1d-conc2 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=659126 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc2 avg latency",
            "value": 0.52,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc2 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=659126 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc2 p99 latency",
            "value": 0.72,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc2 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=659126 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc2 p999 latency",
            "value": 0.83,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc2 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=659126 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc2 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-1p1d-conc2 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=659126 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc4 request throughput",
            "value": 5451.54,
            "unit": "req/s",
            "extra": "cell=pd-chat-1p1d-conc4 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=981277 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc4 avg latency",
            "value": 0.7,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc4 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=981277 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc4 p99 latency",
            "value": 1.17,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc4 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=981277 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc4 p999 latency",
            "value": 1.47,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc4 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=981277 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc4 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-1p1d-conc4 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=981277 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc8 request throughput",
            "value": 6846.91,
            "unit": "req/s",
            "extra": "cell=pd-chat-1p1d-conc8 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1232444 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc8 avg latency",
            "value": 1.13,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc8 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1232444 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc8 p99 latency",
            "value": 2.08,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc8 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1232444 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc8 p999 latency",
            "value": 2.63,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc8 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1232444 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc8 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-1p1d-conc8 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1232444 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc1 request throughput",
            "value": 2278.86,
            "unit": "req/s",
            "extra": "cell=pd-chat-2p1d-conc1 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=410194 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc1 avg latency",
            "value": 0.42,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc1 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=410194 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc1 p99 latency",
            "value": 0.48,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc1 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=410194 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc1 p999 latency",
            "value": 0.52,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc1 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=410194 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc1 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-2p1d-conc1 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=410194 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc16 request throughput",
            "value": 7734.15,
            "unit": "req/s",
            "extra": "cell=pd-chat-2p1d-conc16 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1392147 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc16 avg latency",
            "value": 2.02,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc16 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1392147 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc16 p99 latency",
            "value": 3.78,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc16 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1392147 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc16 p999 latency",
            "value": 4.84,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc16 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1392147 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc16 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-2p1d-conc16 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1392147 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc2 request throughput",
            "value": 3633.26,
            "unit": "req/s",
            "extra": "cell=pd-chat-2p1d-conc2 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=653987 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc2 avg latency",
            "value": 0.53,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc2 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=653987 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc2 p99 latency",
            "value": 0.72,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc2 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=653987 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc2 p999 latency",
            "value": 0.83,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc2 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=653987 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc2 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-2p1d-conc2 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=653987 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc4 request throughput",
            "value": 5350.81,
            "unit": "req/s",
            "extra": "cell=pd-chat-2p1d-conc4 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=963145 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc4 avg latency",
            "value": 0.72,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc4 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=963145 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc4 p99 latency",
            "value": 1.19,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc4 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=963145 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc4 p999 latency",
            "value": 1.51,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc4 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=963145 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc4 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-2p1d-conc4 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=963145 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc8 request throughput",
            "value": 6853.8,
            "unit": "req/s",
            "extra": "cell=pd-chat-2p1d-conc8 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1233684 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc8 avg latency",
            "value": 1.13,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc8 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1233684 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc8 p99 latency",
            "value": 2.08,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc8 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1233684 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc8 p999 latency",
            "value": 2.64,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc8 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1233684 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc8 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-2p1d-conc8 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1233684 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc1 request throughput",
            "value": 2278.65,
            "unit": "req/s",
            "extra": "cell=pd-chat-3p1d-conc1 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=410157 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc1 avg latency",
            "value": 0.42,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc1 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=410157 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc1 p99 latency",
            "value": 0.48,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc1 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=410157 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc1 p999 latency",
            "value": 0.53,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc1 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=410157 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc1 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-3p1d-conc1 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=410157 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc16 request throughput",
            "value": 7753.46,
            "unit": "req/s",
            "extra": "cell=pd-chat-3p1d-conc16 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1395622 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc16 avg latency",
            "value": 2.02,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc16 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1395622 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc16 p99 latency",
            "value": 3.77,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc16 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1395622 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc16 p999 latency",
            "value": 4.8,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc16 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1395622 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc16 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-3p1d-conc16 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1395622 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc2 request throughput",
            "value": 3654.85,
            "unit": "req/s",
            "extra": "cell=pd-chat-3p1d-conc2 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=657873 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc2 avg latency",
            "value": 0.52,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc2 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=657873 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc2 p99 latency",
            "value": 0.72,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc2 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=657873 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc2 p999 latency",
            "value": 0.83,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc2 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=657873 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc2 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-3p1d-conc2 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=657873 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc4 request throughput",
            "value": 5382.58,
            "unit": "req/s",
            "extra": "cell=pd-chat-3p1d-conc4 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=968864 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc4 avg latency",
            "value": 0.71,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc4 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=968864 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc4 p99 latency",
            "value": 1.18,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc4 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=968864 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc4 p999 latency",
            "value": 1.49,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc4 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=968864 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc4 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-3p1d-conc4 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=968864 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc8 request throughput",
            "value": 6824.25,
            "unit": "req/s",
            "extra": "cell=pd-chat-3p1d-conc8 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1228365 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc8 avg latency",
            "value": 1.14,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc8 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1228365 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc8 p99 latency",
            "value": 2.08,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc8 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1228365 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc8 p999 latency",
            "value": 2.63,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc8 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1228365 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc8 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-3p1d-conc8 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1228365 Run: https://github.com/feifei14119/ATOM/actions/runs/28332820886"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "name": "Pleaplusone",
            "username": "ganyi1996ppo",
            "email": "ygan@amd.com"
          },
          "committer": {
            "name": "GitHub",
            "username": "web-flow",
            "email": "noreply@github.com"
          },
          "id": "03a3538243e83fe890d80c7ba2a1a73bc796c00e",
          "message": "[MiniMax-M3] gluon pa with shuffle layout for minimax m3  (#1334)\n\n* docs: revise M3 fp8/gluon port plan for first-class framework compat\n\nReplace the env-gated bolt-on approach with one driven by main's existing\nattention-framework contracts: fp8 selected by config.kv_cache_dtype,\nscales returned via KVCacheTensor, binding through build_kv_cache_tensor/\nbind_kv_cache, insert via the quantized hook, metadata via make_sparse_*\nfactories, frozen custom-op signature, CUDAGraph-safe scratch, byte\naccounting. Adds a 9-point contract checklist mapped to each task.\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n\n* feat(attn): SparseMHAPagedAttentionImpl skeleton + Attention impl_cls override\n\nTask 0 of the MiniMax-M3 fp8 KV cache + gluon PA port. Adds the subclass\nscaffold (SparseMHAPagedAttentionImpl extends PagedAttentionImpl, overriding\nonly rope_cache + dispatch_backend via delegation for now) and an optional\nimpl_cls kwarg on Attention.__init__ so a model can plug in a specialized impl\nwhile reusing the backend's metadata builder. Indexer state lives on the impl.\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n\n* feat(minimax_m3): page-16 constants + fused SHUFFLE KV-insert kernel\n\nTask 1 of the M3 fp8/gluon port. Adds ASM_PAGE_SIZE=16 / PAGES_PER_SPARSE_BLOCK=8\nand grafts the Triton fused Gemma-RMSNorm + partial-NeoX-RoPE + page-16 SHUFFLE\nKV-insert kernel (+ host wrapper) from origin/ganyi/shuffle_kv_cache_fp8_eagle.\nGPU round-trip test validates q_out/index_q_out vs PyTorch ref and K/V/index\ncache scatter at each token slot.\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n\n* feat(minimax_m3): page-16 sparse block-table builders + fused topk EMIT_SPARSE_BT\n\nTask 2 of the M3 fp8/gluon port. Grafts the decode + prefill page-16 sparse\nblock-table builders into sparse_attn.py (each selected logical 128-block expands\nto 8 contiguous physical 16-pages, partial tail packed last, exact context_lens),\nand replaces index_topk.py wholesale with the source-branch version that adds the\nfused EMIT_SPARSE_BT block-table emission and MAX_Q spec-decode causal support\n(both opt-in via defaulted kwargs, so existing decode callers are unaffected).\n\nTests: x8 expansion + tail-last packing + ctx lengths for the standalone builder;\nfused EMIT path matches the standalone builder bit-for-bit (num_kv_heads==1).\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n\n* feat(minimax_m3): gluon PA decode + prefill runners over page-16 SHUFFLE cache\n\nTask 3 of the M3 fp8/gluon port. Grafts minimax_m3_sparse_attn_decode_asm,\nminimax_m3_sparse_attn_prefill_asm, and the shared _run_prefill_fp8_gluon helper\nfrom the source branch: index top-k -> page-16 sparse block table -> AITER gluon\nsplit-KV paged-attention (run_pa_decode_gluon), with fp8 vs bf16 compute_type and\nper-token scales selected by the KV cache dtype. Adds `import aiter` (used for\naiter.dtypes.fp8). Parity test (gluon vs Triton split-K decode reference) for\ngqa 8/16; validated further by the existing asm/fp8/prefill oracle tests.\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n\n* feat(attn): implement SparseMHAPagedAttentionImpl.rope_cache override\n\nTask 4 of the M3 fp8/gluon port. The override runs MiniMax-M3's fused\nqk-norm + partial-NeoX-RoPE + page-16 SHUFFLE KV insert + indexer-key insert via\naiter.fused_qknorm_idxrqknorm (consuming the packed qkv), reading the SHUFFLE\nK/V + scale + index caches off the bound layer. It returns the parent's 7-tuple\n(query rotated) and stashes the rotated indexer query on self._index_q for\ndispatch_backend. fp8 vs bf16 selected by kv_cache_dtype; fp8 writes per-token\ndequant scales into k_scale/v_scale. Adds the _minimax_m3_cos_sin_cache helper.\n\nTest (bf16 + fp8): override returns the 7-tuple, populates _index_q with correct\nshape, and mutates the KV/index caches (+ fp8 scales).\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n\n* feat(attn): implement SparseMHAPagedAttentionImpl.dispatch_backend override\n\nTask 5 of the M3 fp8/gluon port. dispatch_backend returns the M3 sparse\nprefill/decode backend callable (parent contract\nfn(q,k,v,k_cache,v_cache,k_scale,v_scale,fwd_ctx)). Both paths select per-token\ntop-k index blocks with the fused page-16 sparse block-table emit, then run the\ngluon split-KV paged-attention over the SHUFFLE cache; fp8 vs bf16 follows the\ncache dtype inside the runners. Prefill uses the sync-free on-device metadata\nfallback (query_req_id/abs_pos/qo_indptr=None). Consumes self._index_q from\nrope_cache and clears it afterward.\n\nNote: index_cache is page-128 3D [num_logical, 128, idx_head_dim], indexed by the\nlogical block_table in index-topk (distinct from the page-16 SHUFFLE KV cache).\nTest (bf16+fp8): dispatch returns the decode callable; running it yields finite\n[tokens, nh, hd] output and clears _index_q.\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n\n* first version of refactor\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* remove unnecessary files\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* runable and can response resonable output\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* acc right\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* reuse mha's allocation for main cache,  view at use time\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* remove prepare mtp metadata\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* format\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* format\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* resolve comments\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n---------\n\nSigned-off-by: ganyi <ygan@amd.com>\nCo-authored-by: Claude <noreply@anthropic.com>",
          "timestamp": "2026-06-25T02:16:58Z",
          "url": "https://github.com/feifei14119/ATOM/commit/03a3538243e83fe890d80c7ba2a1a73bc796c00e"
        },
        "date": 1782765747316,
        "tool": "customBiggerIsBetter",
        "benches": [
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc1 request throughput",
            "value": 2043.86,
            "unit": "req/s",
            "extra": "cell=pd-chat-1p1d-conc1 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=367894 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc1 avg latency",
            "value": 0.47,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc1 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=367894 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc1 p99 latency",
            "value": 0.92,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc1 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=367894 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc1 p999 latency",
            "value": 2.04,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc1 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=367894 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc1 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-1p1d-conc1 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=367894 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc16 request throughput",
            "value": 8648.16,
            "unit": "req/s",
            "extra": "cell=pd-chat-1p1d-conc16 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1556669 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc16 avg latency",
            "value": 1.8,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc16 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1556669 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc16 p99 latency",
            "value": 3.37,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc16 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1556669 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc16 p999 latency",
            "value": 4.28,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc16 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1556669 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc16 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-1p1d-conc16 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1556669 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc2 request throughput",
            "value": 3747.44,
            "unit": "req/s",
            "extra": "cell=pd-chat-1p1d-conc2 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=674540 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc2 avg latency",
            "value": 0.51,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc2 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=674540 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc2 p99 latency",
            "value": 0.77,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc2 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=674540 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc2 p999 latency",
            "value": 1.15,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc2 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=674540 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc2 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-1p1d-conc2 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=674540 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc4 request throughput",
            "value": 5323.72,
            "unit": "req/s",
            "extra": "cell=pd-chat-1p1d-conc4 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=958269 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc4 avg latency",
            "value": 0.72,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc4 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=958269 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc4 p99 latency",
            "value": 1.43,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc4 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=958269 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc4 p999 latency",
            "value": 2.65,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc4 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=958269 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc4 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-1p1d-conc4 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=958269 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc8 request throughput",
            "value": 7201.22,
            "unit": "req/s",
            "extra": "cell=pd-chat-1p1d-conc8 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1296220 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc8 avg latency",
            "value": 1.07,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc8 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1296220 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc8 p99 latency",
            "value": 2.1,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc8 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1296220 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc8 p999 latency",
            "value": 3.12,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc8 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1296220 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc8 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-1p1d-conc8 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1296220 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc1 request throughput",
            "value": 2298.39,
            "unit": "req/s",
            "extra": "cell=pd-chat-2p1d-conc1 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=413711 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc1 avg latency",
            "value": 0.42,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc1 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=413711 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc1 p99 latency",
            "value": 0.47,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc1 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=413711 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc1 p999 latency",
            "value": 0.57,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc1 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=413711 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc1 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-2p1d-conc1 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=413711 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc16 request throughput",
            "value": 8711.46,
            "unit": "req/s",
            "extra": "cell=pd-chat-2p1d-conc16 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1568063 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc16 avg latency",
            "value": 1.79,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc16 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1568063 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc16 p99 latency",
            "value": 3.34,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc16 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1568063 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc16 p999 latency",
            "value": 4.24,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc16 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1568063 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc16 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-2p1d-conc16 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1568063 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc2 request throughput",
            "value": 3791.49,
            "unit": "req/s",
            "extra": "cell=pd-chat-2p1d-conc2 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=682468 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc2 avg latency",
            "value": 0.5,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc2 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=682468 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc2 p99 latency",
            "value": 0.7,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc2 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=682468 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc2 p999 latency",
            "value": 0.81,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc2 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=682468 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc2 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-2p1d-conc2 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=682468 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc4 request throughput",
            "value": 5844.16,
            "unit": "req/s",
            "extra": "cell=pd-chat-2p1d-conc4 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1051948 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc4 avg latency",
            "value": 0.65,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc4 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1051948 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc4 p99 latency",
            "value": 1.08,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc4 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1051948 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc4 p999 latency",
            "value": 1.36,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc4 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1051948 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc4 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-2p1d-conc4 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1051948 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc8 request throughput",
            "value": 7486.43,
            "unit": "req/s",
            "extra": "cell=pd-chat-2p1d-conc8 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1347557 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc8 avg latency",
            "value": 1.03,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc8 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1347557 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc8 p99 latency",
            "value": 1.9,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc8 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1347557 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc8 p999 latency",
            "value": 2.41,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc8 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1347557 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc8 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-2p1d-conc8 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1347557 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc1 request throughput",
            "value": 2296.72,
            "unit": "req/s",
            "extra": "cell=pd-chat-3p1d-conc1 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=413410 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc1 avg latency",
            "value": 0.42,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc1 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=413410 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc1 p99 latency",
            "value": 0.47,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc1 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=413410 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc1 p999 latency",
            "value": 0.62,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc1 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=413410 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc1 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-3p1d-conc1 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=413410 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc16 request throughput",
            "value": 8621.18,
            "unit": "req/s",
            "extra": "cell=pd-chat-3p1d-conc16 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1551813 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc16 avg latency",
            "value": 1.81,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc16 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1551813 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc16 p99 latency",
            "value": 3.41,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc16 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1551813 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc16 p999 latency",
            "value": 4.34,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc16 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1551813 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc16 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-3p1d-conc16 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1551813 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc2 request throughput",
            "value": 3823.76,
            "unit": "req/s",
            "extra": "cell=pd-chat-3p1d-conc2 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=688276 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc2 avg latency",
            "value": 0.5,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc2 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=688276 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc2 p99 latency",
            "value": 0.69,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc2 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=688276 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc2 p999 latency",
            "value": 0.79,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc2 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=688276 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc2 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-3p1d-conc2 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=688276 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc4 request throughput",
            "value": 5816.15,
            "unit": "req/s",
            "extra": "cell=pd-chat-3p1d-conc4 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1046907 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc4 avg latency",
            "value": 0.66,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc4 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1046907 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc4 p99 latency",
            "value": 1.09,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc4 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1046907 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc4 p999 latency",
            "value": 1.38,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc4 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1046907 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc4 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-3p1d-conc4 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1046907 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc8 request throughput",
            "value": 7494.19,
            "unit": "req/s",
            "extra": "cell=pd-chat-3p1d-conc8 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1348955 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc8 avg latency",
            "value": 1.03,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc8 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1348955 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc8 p99 latency",
            "value": 1.9,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc8 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1348955 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc8 p999 latency",
            "value": 2.45,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc8 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1348955 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc8 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-3p1d-conc8 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1348955 Run: https://github.com/feifei14119/ATOM/actions/runs/28398196497"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "name": "Pleaplusone",
            "username": "ganyi1996ppo",
            "email": "ygan@amd.com"
          },
          "committer": {
            "name": "GitHub",
            "username": "web-flow",
            "email": "noreply@github.com"
          },
          "id": "03a3538243e83fe890d80c7ba2a1a73bc796c00e",
          "message": "[MiniMax-M3] gluon pa with shuffle layout for minimax m3  (#1334)\n\n* docs: revise M3 fp8/gluon port plan for first-class framework compat\n\nReplace the env-gated bolt-on approach with one driven by main's existing\nattention-framework contracts: fp8 selected by config.kv_cache_dtype,\nscales returned via KVCacheTensor, binding through build_kv_cache_tensor/\nbind_kv_cache, insert via the quantized hook, metadata via make_sparse_*\nfactories, frozen custom-op signature, CUDAGraph-safe scratch, byte\naccounting. Adds a 9-point contract checklist mapped to each task.\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n\n* feat(attn): SparseMHAPagedAttentionImpl skeleton + Attention impl_cls override\n\nTask 0 of the MiniMax-M3 fp8 KV cache + gluon PA port. Adds the subclass\nscaffold (SparseMHAPagedAttentionImpl extends PagedAttentionImpl, overriding\nonly rope_cache + dispatch_backend via delegation for now) and an optional\nimpl_cls kwarg on Attention.__init__ so a model can plug in a specialized impl\nwhile reusing the backend's metadata builder. Indexer state lives on the impl.\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n\n* feat(minimax_m3): page-16 constants + fused SHUFFLE KV-insert kernel\n\nTask 1 of the M3 fp8/gluon port. Adds ASM_PAGE_SIZE=16 / PAGES_PER_SPARSE_BLOCK=8\nand grafts the Triton fused Gemma-RMSNorm + partial-NeoX-RoPE + page-16 SHUFFLE\nKV-insert kernel (+ host wrapper) from origin/ganyi/shuffle_kv_cache_fp8_eagle.\nGPU round-trip test validates q_out/index_q_out vs PyTorch ref and K/V/index\ncache scatter at each token slot.\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n\n* feat(minimax_m3): page-16 sparse block-table builders + fused topk EMIT_SPARSE_BT\n\nTask 2 of the M3 fp8/gluon port. Grafts the decode + prefill page-16 sparse\nblock-table builders into sparse_attn.py (each selected logical 128-block expands\nto 8 contiguous physical 16-pages, partial tail packed last, exact context_lens),\nand replaces index_topk.py wholesale with the source-branch version that adds the\nfused EMIT_SPARSE_BT block-table emission and MAX_Q spec-decode causal support\n(both opt-in via defaulted kwargs, so existing decode callers are unaffected).\n\nTests: x8 expansion + tail-last packing + ctx lengths for the standalone builder;\nfused EMIT path matches the standalone builder bit-for-bit (num_kv_heads==1).\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n\n* feat(minimax_m3): gluon PA decode + prefill runners over page-16 SHUFFLE cache\n\nTask 3 of the M3 fp8/gluon port. Grafts minimax_m3_sparse_attn_decode_asm,\nminimax_m3_sparse_attn_prefill_asm, and the shared _run_prefill_fp8_gluon helper\nfrom the source branch: index top-k -> page-16 sparse block table -> AITER gluon\nsplit-KV paged-attention (run_pa_decode_gluon), with fp8 vs bf16 compute_type and\nper-token scales selected by the KV cache dtype. Adds `import aiter` (used for\naiter.dtypes.fp8). Parity test (gluon vs Triton split-K decode reference) for\ngqa 8/16; validated further by the existing asm/fp8/prefill oracle tests.\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n\n* feat(attn): implement SparseMHAPagedAttentionImpl.rope_cache override\n\nTask 4 of the M3 fp8/gluon port. The override runs MiniMax-M3's fused\nqk-norm + partial-NeoX-RoPE + page-16 SHUFFLE KV insert + indexer-key insert via\naiter.fused_qknorm_idxrqknorm (consuming the packed qkv), reading the SHUFFLE\nK/V + scale + index caches off the bound layer. It returns the parent's 7-tuple\n(query rotated) and stashes the rotated indexer query on self._index_q for\ndispatch_backend. fp8 vs bf16 selected by kv_cache_dtype; fp8 writes per-token\ndequant scales into k_scale/v_scale. Adds the _minimax_m3_cos_sin_cache helper.\n\nTest (bf16 + fp8): override returns the 7-tuple, populates _index_q with correct\nshape, and mutates the KV/index caches (+ fp8 scales).\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n\n* feat(attn): implement SparseMHAPagedAttentionImpl.dispatch_backend override\n\nTask 5 of the M3 fp8/gluon port. dispatch_backend returns the M3 sparse\nprefill/decode backend callable (parent contract\nfn(q,k,v,k_cache,v_cache,k_scale,v_scale,fwd_ctx)). Both paths select per-token\ntop-k index blocks with the fused page-16 sparse block-table emit, then run the\ngluon split-KV paged-attention over the SHUFFLE cache; fp8 vs bf16 follows the\ncache dtype inside the runners. Prefill uses the sync-free on-device metadata\nfallback (query_req_id/abs_pos/qo_indptr=None). Consumes self._index_q from\nrope_cache and clears it afterward.\n\nNote: index_cache is page-128 3D [num_logical, 128, idx_head_dim], indexed by the\nlogical block_table in index-topk (distinct from the page-16 SHUFFLE KV cache).\nTest (bf16+fp8): dispatch returns the decode callable; running it yields finite\n[tokens, nh, hd] output and clears _index_q.\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n\n* first version of refactor\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* remove unnecessary files\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* runable and can response resonable output\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* acc right\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* reuse mha's allocation for main cache,  view at use time\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* remove prepare mtp metadata\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* format\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* format\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* resolve comments\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n---------\n\nSigned-off-by: ganyi <ygan@amd.com>\nCo-authored-by: Claude <noreply@anthropic.com>",
          "timestamp": "2026-06-25T02:16:58Z",
          "url": "https://github.com/feifei14119/ATOM/commit/03a3538243e83fe890d80c7ba2a1a73bc796c00e"
        },
        "date": 1782852147018,
        "tool": "customBiggerIsBetter",
        "benches": [
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc1 request throughput",
            "value": 2147.09,
            "unit": "req/s",
            "extra": "cell=pd-chat-1p1d-conc1 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=386477 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc1 avg latency",
            "value": 0.45,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc1 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=386477 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc1 p99 latency",
            "value": 0.51,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc1 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=386477 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc1 p999 latency",
            "value": 0.56,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc1 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=386477 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc1 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-1p1d-conc1 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=386477 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc16 request throughput",
            "value": 7624.61,
            "unit": "req/s",
            "extra": "cell=pd-chat-1p1d-conc16 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1372430 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc16 avg latency",
            "value": 2.05,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc16 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1372430 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc16 p99 latency",
            "value": 3.84,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc16 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1372430 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc16 p999 latency",
            "value": 4.86,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc16 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1372430 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc16 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-1p1d-conc16 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1372430 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc2 request throughput",
            "value": 3515.88,
            "unit": "req/s",
            "extra": "cell=pd-chat-1p1d-conc2 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=632859 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc2 avg latency",
            "value": 0.54,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc2 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=632859 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc2 p99 latency",
            "value": 0.75,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc2 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=632859 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc2 p999 latency",
            "value": 0.86,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc2 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=632859 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc2 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-1p1d-conc2 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=632859 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc4 request throughput",
            "value": 5304.81,
            "unit": "req/s",
            "extra": "cell=pd-chat-1p1d-conc4 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=954865 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc4 avg latency",
            "value": 0.72,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc4 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=954865 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc4 p99 latency",
            "value": 1.2,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc4 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=954865 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc4 p999 latency",
            "value": 1.5,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc4 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=954865 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc4 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-1p1d-conc4 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=954865 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc8 request throughput",
            "value": 6724.03,
            "unit": "req/s",
            "extra": "cell=pd-chat-1p1d-conc8 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1210326 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc8 avg latency",
            "value": 1.15,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc8 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1210326 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc8 p99 latency",
            "value": 2.12,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc8 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1210326 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc8 p999 latency",
            "value": 2.69,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc8 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1210326 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc8 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-1p1d-conc8 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1210326 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc1 request throughput",
            "value": 2152.96,
            "unit": "req/s",
            "extra": "cell=pd-chat-2p1d-conc1 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=387532 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc1 avg latency",
            "value": 0.45,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc1 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=387532 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc1 p99 latency",
            "value": 0.51,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc1 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=387532 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc1 p999 latency",
            "value": 0.55,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc1 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=387532 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc1 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-2p1d-conc1 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=387532 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc16 request throughput",
            "value": 7694.31,
            "unit": "req/s",
            "extra": "cell=pd-chat-2p1d-conc16 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1384975 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc16 avg latency",
            "value": 2.03,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc16 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1384975 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc16 p99 latency",
            "value": 3.8,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc16 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1384975 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc16 p999 latency",
            "value": 4.84,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc16 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1384975 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc16 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-2p1d-conc16 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1384975 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc2 request throughput",
            "value": 3488.58,
            "unit": "req/s",
            "extra": "cell=pd-chat-2p1d-conc2 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=627945 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc2 avg latency",
            "value": 0.55,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc2 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=627945 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc2 p99 latency",
            "value": 0.75,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc2 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=627945 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc2 p999 latency",
            "value": 0.86,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc2 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=627945 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc2 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-2p1d-conc2 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=627945 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc4 request throughput",
            "value": 5279.25,
            "unit": "req/s",
            "extra": "cell=pd-chat-2p1d-conc4 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=950265 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc4 avg latency",
            "value": 0.73,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc4 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=950265 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc4 p99 latency",
            "value": 1.21,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc4 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=950265 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc4 p999 latency",
            "value": 1.52,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc4 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=950265 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc4 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-2p1d-conc4 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=950265 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc8 request throughput",
            "value": 6729.36,
            "unit": "req/s",
            "extra": "cell=pd-chat-2p1d-conc8 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1211285 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc8 avg latency",
            "value": 1.15,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc8 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1211285 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc8 p99 latency",
            "value": 2.12,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc8 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1211285 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc8 p999 latency",
            "value": 2.68,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc8 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1211285 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc8 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-2p1d-conc8 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1211285 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc1 request throughput",
            "value": 2143.96,
            "unit": "req/s",
            "extra": "cell=pd-chat-3p1d-conc1 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=385912 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc1 avg latency",
            "value": 0.45,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc1 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=385912 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc1 p99 latency",
            "value": 0.51,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc1 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=385912 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc1 p999 latency",
            "value": 0.55,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc1 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=385912 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc1 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-3p1d-conc1 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=385912 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc16 request throughput",
            "value": 7611.72,
            "unit": "req/s",
            "extra": "cell=pd-chat-3p1d-conc16 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1370110 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc16 avg latency",
            "value": 2.06,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc16 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1370110 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc16 p99 latency",
            "value": 3.84,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc16 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1370110 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc16 p999 latency",
            "value": 4.89,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc16 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1370110 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc16 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-3p1d-conc16 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1370110 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc2 request throughput",
            "value": 3506.58,
            "unit": "req/s",
            "extra": "cell=pd-chat-3p1d-conc2 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=631185 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc2 avg latency",
            "value": 0.55,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc2 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=631185 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc2 p99 latency",
            "value": 0.75,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc2 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=631185 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc2 p999 latency",
            "value": 0.86,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc2 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=631185 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc2 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-3p1d-conc2 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=631185 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc4 request throughput",
            "value": 5314.38,
            "unit": "req/s",
            "extra": "cell=pd-chat-3p1d-conc4 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=956589 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc4 avg latency",
            "value": 0.72,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc4 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=956589 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc4 p99 latency",
            "value": 1.2,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc4 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=956589 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc4 p999 latency",
            "value": 1.51,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc4 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=956589 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc4 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-3p1d-conc4 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=956589 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc8 request throughput",
            "value": 6657.92,
            "unit": "req/s",
            "extra": "cell=pd-chat-3p1d-conc8 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1198426 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc8 avg latency",
            "value": 1.16,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc8 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1198426 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc8 p99 latency",
            "value": 2.14,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc8 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1198426 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc8 p999 latency",
            "value": 2.71,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc8 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1198426 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc8 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-3p1d-conc8 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1198426 Run: https://github.com/feifei14119/ATOM/actions/runs/28471299659"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "name": "Pleaplusone",
            "username": "ganyi1996ppo",
            "email": "ygan@amd.com"
          },
          "committer": {
            "name": "GitHub",
            "username": "web-flow",
            "email": "noreply@github.com"
          },
          "id": "03a3538243e83fe890d80c7ba2a1a73bc796c00e",
          "message": "[MiniMax-M3] gluon pa with shuffle layout for minimax m3  (#1334)\n\n* docs: revise M3 fp8/gluon port plan for first-class framework compat\n\nReplace the env-gated bolt-on approach with one driven by main's existing\nattention-framework contracts: fp8 selected by config.kv_cache_dtype,\nscales returned via KVCacheTensor, binding through build_kv_cache_tensor/\nbind_kv_cache, insert via the quantized hook, metadata via make_sparse_*\nfactories, frozen custom-op signature, CUDAGraph-safe scratch, byte\naccounting. Adds a 9-point contract checklist mapped to each task.\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n\n* feat(attn): SparseMHAPagedAttentionImpl skeleton + Attention impl_cls override\n\nTask 0 of the MiniMax-M3 fp8 KV cache + gluon PA port. Adds the subclass\nscaffold (SparseMHAPagedAttentionImpl extends PagedAttentionImpl, overriding\nonly rope_cache + dispatch_backend via delegation for now) and an optional\nimpl_cls kwarg on Attention.__init__ so a model can plug in a specialized impl\nwhile reusing the backend's metadata builder. Indexer state lives on the impl.\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n\n* feat(minimax_m3): page-16 constants + fused SHUFFLE KV-insert kernel\n\nTask 1 of the M3 fp8/gluon port. Adds ASM_PAGE_SIZE=16 / PAGES_PER_SPARSE_BLOCK=8\nand grafts the Triton fused Gemma-RMSNorm + partial-NeoX-RoPE + page-16 SHUFFLE\nKV-insert kernel (+ host wrapper) from origin/ganyi/shuffle_kv_cache_fp8_eagle.\nGPU round-trip test validates q_out/index_q_out vs PyTorch ref and K/V/index\ncache scatter at each token slot.\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n\n* feat(minimax_m3): page-16 sparse block-table builders + fused topk EMIT_SPARSE_BT\n\nTask 2 of the M3 fp8/gluon port. Grafts the decode + prefill page-16 sparse\nblock-table builders into sparse_attn.py (each selected logical 128-block expands\nto 8 contiguous physical 16-pages, partial tail packed last, exact context_lens),\nand replaces index_topk.py wholesale with the source-branch version that adds the\nfused EMIT_SPARSE_BT block-table emission and MAX_Q spec-decode causal support\n(both opt-in via defaulted kwargs, so existing decode callers are unaffected).\n\nTests: x8 expansion + tail-last packing + ctx lengths for the standalone builder;\nfused EMIT path matches the standalone builder bit-for-bit (num_kv_heads==1).\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n\n* feat(minimax_m3): gluon PA decode + prefill runners over page-16 SHUFFLE cache\n\nTask 3 of the M3 fp8/gluon port. Grafts minimax_m3_sparse_attn_decode_asm,\nminimax_m3_sparse_attn_prefill_asm, and the shared _run_prefill_fp8_gluon helper\nfrom the source branch: index top-k -> page-16 sparse block table -> AITER gluon\nsplit-KV paged-attention (run_pa_decode_gluon), with fp8 vs bf16 compute_type and\nper-token scales selected by the KV cache dtype. Adds `import aiter` (used for\naiter.dtypes.fp8). Parity test (gluon vs Triton split-K decode reference) for\ngqa 8/16; validated further by the existing asm/fp8/prefill oracle tests.\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n\n* feat(attn): implement SparseMHAPagedAttentionImpl.rope_cache override\n\nTask 4 of the M3 fp8/gluon port. The override runs MiniMax-M3's fused\nqk-norm + partial-NeoX-RoPE + page-16 SHUFFLE KV insert + indexer-key insert via\naiter.fused_qknorm_idxrqknorm (consuming the packed qkv), reading the SHUFFLE\nK/V + scale + index caches off the bound layer. It returns the parent's 7-tuple\n(query rotated) and stashes the rotated indexer query on self._index_q for\ndispatch_backend. fp8 vs bf16 selected by kv_cache_dtype; fp8 writes per-token\ndequant scales into k_scale/v_scale. Adds the _minimax_m3_cos_sin_cache helper.\n\nTest (bf16 + fp8): override returns the 7-tuple, populates _index_q with correct\nshape, and mutates the KV/index caches (+ fp8 scales).\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n\n* feat(attn): implement SparseMHAPagedAttentionImpl.dispatch_backend override\n\nTask 5 of the M3 fp8/gluon port. dispatch_backend returns the M3 sparse\nprefill/decode backend callable (parent contract\nfn(q,k,v,k_cache,v_cache,k_scale,v_scale,fwd_ctx)). Both paths select per-token\ntop-k index blocks with the fused page-16 sparse block-table emit, then run the\ngluon split-KV paged-attention over the SHUFFLE cache; fp8 vs bf16 follows the\ncache dtype inside the runners. Prefill uses the sync-free on-device metadata\nfallback (query_req_id/abs_pos/qo_indptr=None). Consumes self._index_q from\nrope_cache and clears it afterward.\n\nNote: index_cache is page-128 3D [num_logical, 128, idx_head_dim], indexed by the\nlogical block_table in index-topk (distinct from the page-16 SHUFFLE KV cache).\nTest (bf16+fp8): dispatch returns the decode callable; running it yields finite\n[tokens, nh, hd] output and clears _index_q.\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n\n* first version of refactor\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* remove unnecessary files\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* runable and can response resonable output\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* acc right\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* reuse mha's allocation for main cache,  view at use time\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* remove prepare mtp metadata\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* format\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* format\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* resolve comments\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n---------\n\nSigned-off-by: ganyi <ygan@amd.com>\nCo-authored-by: Claude <noreply@anthropic.com>",
          "timestamp": "2026-06-25T02:16:58Z",
          "url": "https://github.com/feifei14119/ATOM/commit/03a3538243e83fe890d80c7ba2a1a73bc796c00e"
        },
        "date": 1782938403201,
        "tool": "customBiggerIsBetter",
        "benches": [
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc1 request throughput",
            "value": 2109.82,
            "unit": "req/s",
            "extra": "cell=pd-chat-1p1d-conc1 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=379767 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc1 avg latency",
            "value": 0.46,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc1 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=379767 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc1 p99 latency",
            "value": 0.52,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc1 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=379767 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc1 p999 latency",
            "value": 0.57,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc1 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=379767 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc1 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-1p1d-conc1 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=379767 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc16 request throughput",
            "value": 7480.49,
            "unit": "req/s",
            "extra": "cell=pd-chat-1p1d-conc16 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1346489 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc16 avg latency",
            "value": 2.09,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc16 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1346489 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc16 p99 latency",
            "value": 3.9,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc16 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1346489 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc16 p999 latency",
            "value": 4.99,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc16 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1346489 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc16 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-1p1d-conc16 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1346489 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc2 request throughput",
            "value": 3463.71,
            "unit": "req/s",
            "extra": "cell=pd-chat-1p1d-conc2 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=623467 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc2 avg latency",
            "value": 0.55,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc2 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=623467 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc2 p99 latency",
            "value": 0.76,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc2 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=623467 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc2 p999 latency",
            "value": 0.88,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc2 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=623467 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc2 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-1p1d-conc2 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=623467 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc4 request throughput",
            "value": 5254.42,
            "unit": "req/s",
            "extra": "cell=pd-chat-1p1d-conc4 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=945795 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc4 avg latency",
            "value": 0.73,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc4 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=945795 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc4 p99 latency",
            "value": 1.21,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc4 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=945795 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc4 p999 latency",
            "value": 1.53,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc4 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=945795 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc4 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-1p1d-conc4 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=945795 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc8 request throughput",
            "value": 6575.47,
            "unit": "req/s",
            "extra": "cell=pd-chat-1p1d-conc8 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1183585 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc8 avg latency",
            "value": 1.18,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc8 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1183585 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc8 p99 latency",
            "value": 2.16,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc8 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1183585 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc8 p999 latency",
            "value": 2.74,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc8 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1183585 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc8 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-1p1d-conc8 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1183585 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc1 request throughput",
            "value": 2089.32,
            "unit": "req/s",
            "extra": "cell=pd-chat-2p1d-conc1 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=376077 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc1 avg latency",
            "value": 0.46,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc1 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=376077 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc1 p99 latency",
            "value": 0.52,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc1 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=376077 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc1 p999 latency",
            "value": 0.58,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc1 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=376077 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc1 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-2p1d-conc1 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=376077 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc16 request throughput",
            "value": 7646.21,
            "unit": "req/s",
            "extra": "cell=pd-chat-2p1d-conc16 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1376317 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc16 avg latency",
            "value": 2.05,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc16 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1376317 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc16 p99 latency",
            "value": 3.83,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc16 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1376317 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc16 p999 latency",
            "value": 4.9,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc16 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1376317 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc16 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-2p1d-conc16 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1376317 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc2 request throughput",
            "value": 3438.88,
            "unit": "req/s",
            "extra": "cell=pd-chat-2p1d-conc2 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=618999 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc2 avg latency",
            "value": 0.56,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc2 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=618999 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc2 p99 latency",
            "value": 0.76,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc2 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=618999 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc2 p999 latency",
            "value": 0.87,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc2 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=618999 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc2 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-2p1d-conc2 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=618999 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc4 request throughput",
            "value": 5208.93,
            "unit": "req/s",
            "extra": "cell=pd-chat-2p1d-conc4 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=937608 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc4 avg latency",
            "value": 0.74,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc4 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=937608 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc4 p99 latency",
            "value": 1.23,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc4 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=937608 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc4 p999 latency",
            "value": 1.54,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc4 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=937608 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc4 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-2p1d-conc4 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=937608 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc8 request throughput",
            "value": 6611.95,
            "unit": "req/s",
            "extra": "cell=pd-chat-2p1d-conc8 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1190151 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc8 avg latency",
            "value": 1.17,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc8 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1190151 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc8 p99 latency",
            "value": 2.15,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc8 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1190151 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc8 p999 latency",
            "value": 2.74,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc8 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1190151 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc8 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-2p1d-conc8 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1190151 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc1 request throughput",
            "value": 2096.47,
            "unit": "req/s",
            "extra": "cell=pd-chat-3p1d-conc1 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=377365 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc1 avg latency",
            "value": 0.46,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc1 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=377365 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc1 p99 latency",
            "value": 0.52,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc1 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=377365 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc1 p999 latency",
            "value": 0.58,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc1 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=377365 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc1 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-3p1d-conc1 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=377365 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc16 request throughput",
            "value": 7504.6,
            "unit": "req/s",
            "extra": "cell=pd-chat-3p1d-conc16 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1350828 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc16 avg latency",
            "value": 2.08,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc16 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1350828 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc16 p99 latency",
            "value": 3.89,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc16 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1350828 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc16 p999 latency",
            "value": 4.96,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc16 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1350828 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc16 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-3p1d-conc16 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1350828 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc2 request throughput",
            "value": 3422.23,
            "unit": "req/s",
            "extra": "cell=pd-chat-3p1d-conc2 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=616001 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc2 avg latency",
            "value": 0.56,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc2 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=616001 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc2 p99 latency",
            "value": 0.77,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc2 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=616001 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc2 p999 latency",
            "value": 0.89,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc2 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=616001 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc2 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-3p1d-conc2 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=616001 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc4 request throughput",
            "value": 5262.31,
            "unit": "req/s",
            "extra": "cell=pd-chat-3p1d-conc4 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=947216 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc4 avg latency",
            "value": 0.73,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc4 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=947216 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc4 p99 latency",
            "value": 1.21,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc4 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=947216 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc4 p999 latency",
            "value": 1.52,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc4 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=947216 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc4 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-3p1d-conc4 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=947216 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc8 request throughput",
            "value": 6631.7,
            "unit": "req/s",
            "extra": "cell=pd-chat-3p1d-conc8 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1193706 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc8 avg latency",
            "value": 1.17,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc8 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1193706 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc8 p99 latency",
            "value": 2.15,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc8 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1193706 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc8 p999 latency",
            "value": 2.72,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc8 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1193706 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc8 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-3p1d-conc8 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1193706 Run: https://github.com/feifei14119/ATOM/actions/runs/28543175529"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "name": "Pleaplusone",
            "username": "ganyi1996ppo",
            "email": "ygan@amd.com"
          },
          "committer": {
            "name": "GitHub",
            "username": "web-flow",
            "email": "noreply@github.com"
          },
          "id": "03a3538243e83fe890d80c7ba2a1a73bc796c00e",
          "message": "[MiniMax-M3] gluon pa with shuffle layout for minimax m3  (#1334)\n\n* docs: revise M3 fp8/gluon port plan for first-class framework compat\n\nReplace the env-gated bolt-on approach with one driven by main's existing\nattention-framework contracts: fp8 selected by config.kv_cache_dtype,\nscales returned via KVCacheTensor, binding through build_kv_cache_tensor/\nbind_kv_cache, insert via the quantized hook, metadata via make_sparse_*\nfactories, frozen custom-op signature, CUDAGraph-safe scratch, byte\naccounting. Adds a 9-point contract checklist mapped to each task.\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n\n* feat(attn): SparseMHAPagedAttentionImpl skeleton + Attention impl_cls override\n\nTask 0 of the MiniMax-M3 fp8 KV cache + gluon PA port. Adds the subclass\nscaffold (SparseMHAPagedAttentionImpl extends PagedAttentionImpl, overriding\nonly rope_cache + dispatch_backend via delegation for now) and an optional\nimpl_cls kwarg on Attention.__init__ so a model can plug in a specialized impl\nwhile reusing the backend's metadata builder. Indexer state lives on the impl.\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n\n* feat(minimax_m3): page-16 constants + fused SHUFFLE KV-insert kernel\n\nTask 1 of the M3 fp8/gluon port. Adds ASM_PAGE_SIZE=16 / PAGES_PER_SPARSE_BLOCK=8\nand grafts the Triton fused Gemma-RMSNorm + partial-NeoX-RoPE + page-16 SHUFFLE\nKV-insert kernel (+ host wrapper) from origin/ganyi/shuffle_kv_cache_fp8_eagle.\nGPU round-trip test validates q_out/index_q_out vs PyTorch ref and K/V/index\ncache scatter at each token slot.\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n\n* feat(minimax_m3): page-16 sparse block-table builders + fused topk EMIT_SPARSE_BT\n\nTask 2 of the M3 fp8/gluon port. Grafts the decode + prefill page-16 sparse\nblock-table builders into sparse_attn.py (each selected logical 128-block expands\nto 8 contiguous physical 16-pages, partial tail packed last, exact context_lens),\nand replaces index_topk.py wholesale with the source-branch version that adds the\nfused EMIT_SPARSE_BT block-table emission and MAX_Q spec-decode causal support\n(both opt-in via defaulted kwargs, so existing decode callers are unaffected).\n\nTests: x8 expansion + tail-last packing + ctx lengths for the standalone builder;\nfused EMIT path matches the standalone builder bit-for-bit (num_kv_heads==1).\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n\n* feat(minimax_m3): gluon PA decode + prefill runners over page-16 SHUFFLE cache\n\nTask 3 of the M3 fp8/gluon port. Grafts minimax_m3_sparse_attn_decode_asm,\nminimax_m3_sparse_attn_prefill_asm, and the shared _run_prefill_fp8_gluon helper\nfrom the source branch: index top-k -> page-16 sparse block table -> AITER gluon\nsplit-KV paged-attention (run_pa_decode_gluon), with fp8 vs bf16 compute_type and\nper-token scales selected by the KV cache dtype. Adds `import aiter` (used for\naiter.dtypes.fp8). Parity test (gluon vs Triton split-K decode reference) for\ngqa 8/16; validated further by the existing asm/fp8/prefill oracle tests.\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n\n* feat(attn): implement SparseMHAPagedAttentionImpl.rope_cache override\n\nTask 4 of the M3 fp8/gluon port. The override runs MiniMax-M3's fused\nqk-norm + partial-NeoX-RoPE + page-16 SHUFFLE KV insert + indexer-key insert via\naiter.fused_qknorm_idxrqknorm (consuming the packed qkv), reading the SHUFFLE\nK/V + scale + index caches off the bound layer. It returns the parent's 7-tuple\n(query rotated) and stashes the rotated indexer query on self._index_q for\ndispatch_backend. fp8 vs bf16 selected by kv_cache_dtype; fp8 writes per-token\ndequant scales into k_scale/v_scale. Adds the _minimax_m3_cos_sin_cache helper.\n\nTest (bf16 + fp8): override returns the 7-tuple, populates _index_q with correct\nshape, and mutates the KV/index caches (+ fp8 scales).\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n\n* feat(attn): implement SparseMHAPagedAttentionImpl.dispatch_backend override\n\nTask 5 of the M3 fp8/gluon port. dispatch_backend returns the M3 sparse\nprefill/decode backend callable (parent contract\nfn(q,k,v,k_cache,v_cache,k_scale,v_scale,fwd_ctx)). Both paths select per-token\ntop-k index blocks with the fused page-16 sparse block-table emit, then run the\ngluon split-KV paged-attention over the SHUFFLE cache; fp8 vs bf16 follows the\ncache dtype inside the runners. Prefill uses the sync-free on-device metadata\nfallback (query_req_id/abs_pos/qo_indptr=None). Consumes self._index_q from\nrope_cache and clears it afterward.\n\nNote: index_cache is page-128 3D [num_logical, 128, idx_head_dim], indexed by the\nlogical block_table in index-topk (distinct from the page-16 SHUFFLE KV cache).\nTest (bf16+fp8): dispatch returns the decode callable; running it yields finite\n[tokens, nh, hd] output and clears _index_q.\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n\n* first version of refactor\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* remove unnecessary files\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* runable and can response resonable output\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* acc right\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* reuse mha's allocation for main cache,  view at use time\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* remove prepare mtp metadata\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* format\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* format\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* resolve comments\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n---------\n\nSigned-off-by: ganyi <ygan@amd.com>\nCo-authored-by: Claude <noreply@anthropic.com>",
          "timestamp": "2026-06-25T02:16:58Z",
          "url": "https://github.com/feifei14119/ATOM/commit/03a3538243e83fe890d80c7ba2a1a73bc796c00e"
        },
        "date": 1783023047471,
        "tool": "customBiggerIsBetter",
        "benches": [
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc1 request throughput",
            "value": 2294.58,
            "unit": "req/s",
            "extra": "cell=pd-chat-1p1d-conc1 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=413024 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc1 avg latency",
            "value": 0.42,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc1 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=413024 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc1 p99 latency",
            "value": 0.46,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc1 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=413024 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc1 p999 latency",
            "value": 0.54,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc1 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=413024 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc1 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-1p1d-conc1 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=413024 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc16 request throughput",
            "value": 8850.63,
            "unit": "req/s",
            "extra": "cell=pd-chat-1p1d-conc16 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1593114 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc16 avg latency",
            "value": 1.77,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc16 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1593114 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc16 p99 latency",
            "value": 3.27,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc16 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1593114 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc16 p999 latency",
            "value": 4.15,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc16 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1593114 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc16 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-1p1d-conc16 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1593114 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc2 request throughput",
            "value": 3784.96,
            "unit": "req/s",
            "extra": "cell=pd-chat-1p1d-conc2 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=681293 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc2 avg latency",
            "value": 0.5,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc2 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=681293 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc2 p99 latency",
            "value": 0.7,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc2 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=681293 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc2 p999 latency",
            "value": 0.8,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc2 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=681293 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc2 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-1p1d-conc2 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=681293 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc4 request throughput",
            "value": 5736.82,
            "unit": "req/s",
            "extra": "cell=pd-chat-1p1d-conc4 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1032628 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc4 avg latency",
            "value": 0.67,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc4 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1032628 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc4 p99 latency",
            "value": 1.11,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc4 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1032628 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc4 p999 latency",
            "value": 1.43,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc4 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1032628 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc4 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-1p1d-conc4 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1032628 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc8 request throughput",
            "value": 7391.28,
            "unit": "req/s",
            "extra": "cell=pd-chat-1p1d-conc8 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1330431 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc8 avg latency",
            "value": 1.04,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc8 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1330431 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc8 p99 latency",
            "value": 1.91,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc8 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1330431 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc8 p999 latency",
            "value": 2.41,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc8 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1330431 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc8 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-1p1d-conc8 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1330431 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc1 request throughput",
            "value": 2300.62,
            "unit": "req/s",
            "extra": "cell=pd-chat-2p1d-conc1 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=414112 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc1 avg latency",
            "value": 0.42,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc1 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=414112 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc1 p99 latency",
            "value": 0.46,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc1 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=414112 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc1 p999 latency",
            "value": 0.5,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc1 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=414112 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc1 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-2p1d-conc1 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=414112 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc16 request throughput",
            "value": 8859.12,
            "unit": "req/s",
            "extra": "cell=pd-chat-2p1d-conc16 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1594641 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc16 avg latency",
            "value": 1.76,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc16 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1594641 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc16 p99 latency",
            "value": 3.28,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc16 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1594641 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc16 p999 latency",
            "value": 4.2,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc16 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1594641 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc16 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-2p1d-conc16 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1594641 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc2 request throughput",
            "value": 3785.93,
            "unit": "req/s",
            "extra": "cell=pd-chat-2p1d-conc2 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=681467 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc2 avg latency",
            "value": 0.5,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc2 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=681467 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc2 p99 latency",
            "value": 0.69,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc2 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=681467 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc2 p999 latency",
            "value": 0.8,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc2 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=681467 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc2 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-2p1d-conc2 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=681467 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc4 request throughput",
            "value": 5723.1,
            "unit": "req/s",
            "extra": "cell=pd-chat-2p1d-conc4 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1030158 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc4 avg latency",
            "value": 0.67,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc4 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1030158 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc4 p99 latency",
            "value": 1.1,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc4 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1030158 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc4 p999 latency",
            "value": 1.38,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc4 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1030158 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc4 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-2p1d-conc4 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1030158 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc8 request throughput",
            "value": 7494.47,
            "unit": "req/s",
            "extra": "cell=pd-chat-2p1d-conc8 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1349004 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc8 avg latency",
            "value": 1.03,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc8 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1349004 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc8 p99 latency",
            "value": 1.89,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc8 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1349004 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc8 p999 latency",
            "value": 2.4,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc8 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1349004 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc8 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-2p1d-conc8 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1349004 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc1 request throughput",
            "value": 2293.02,
            "unit": "req/s",
            "extra": "cell=pd-chat-3p1d-conc1 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=412744 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc1 avg latency",
            "value": 0.42,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc1 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=412744 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc1 p99 latency",
            "value": 0.46,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc1 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=412744 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc1 p999 latency",
            "value": 0.51,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc1 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=412744 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc1 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-3p1d-conc1 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=412744 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc16 request throughput",
            "value": 8783.31,
            "unit": "req/s",
            "extra": "cell=pd-chat-3p1d-conc16 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1580996 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc16 avg latency",
            "value": 1.78,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc16 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1580996 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc16 p99 latency",
            "value": 3.29,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc16 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1580996 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc16 p999 latency",
            "value": 4.19,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc16 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1580996 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc16 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-3p1d-conc16 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1580996 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc2 request throughput",
            "value": 3788.78,
            "unit": "req/s",
            "extra": "cell=pd-chat-3p1d-conc2 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=681981 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc2 avg latency",
            "value": 0.5,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc2 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=681981 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc2 p99 latency",
            "value": 0.69,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc2 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=681981 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc2 p999 latency",
            "value": 0.79,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc2 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=681981 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc2 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-3p1d-conc2 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=681981 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc4 request throughput",
            "value": 5740.17,
            "unit": "req/s",
            "extra": "cell=pd-chat-3p1d-conc4 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1033230 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc4 avg latency",
            "value": 0.67,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc4 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1033230 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc4 p99 latency",
            "value": 1.1,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc4 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1033230 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc4 p999 latency",
            "value": 1.39,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc4 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1033230 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc4 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-3p1d-conc4 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1033230 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc8 request throughput",
            "value": 7500.39,
            "unit": "req/s",
            "extra": "cell=pd-chat-3p1d-conc8 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1350070 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc8 avg latency",
            "value": 1.03,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc8 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1350070 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc8 p99 latency",
            "value": 1.88,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc8 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1350070 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc8 p999 latency",
            "value": 2.36,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc8 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1350070 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc8 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-3p1d-conc8 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1350070 Run: https://github.com/feifei14119/ATOM/actions/runs/28615290415"
          }
        ]
      },
      {
        "commit": {
          "author": {
            "name": "Pleaplusone",
            "username": "ganyi1996ppo",
            "email": "ygan@amd.com"
          },
          "committer": {
            "name": "GitHub",
            "username": "web-flow",
            "email": "noreply@github.com"
          },
          "id": "03a3538243e83fe890d80c7ba2a1a73bc796c00e",
          "message": "[MiniMax-M3] gluon pa with shuffle layout for minimax m3  (#1334)\n\n* docs: revise M3 fp8/gluon port plan for first-class framework compat\n\nReplace the env-gated bolt-on approach with one driven by main's existing\nattention-framework contracts: fp8 selected by config.kv_cache_dtype,\nscales returned via KVCacheTensor, binding through build_kv_cache_tensor/\nbind_kv_cache, insert via the quantized hook, metadata via make_sparse_*\nfactories, frozen custom-op signature, CUDAGraph-safe scratch, byte\naccounting. Adds a 9-point contract checklist mapped to each task.\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n\n* feat(attn): SparseMHAPagedAttentionImpl skeleton + Attention impl_cls override\n\nTask 0 of the MiniMax-M3 fp8 KV cache + gluon PA port. Adds the subclass\nscaffold (SparseMHAPagedAttentionImpl extends PagedAttentionImpl, overriding\nonly rope_cache + dispatch_backend via delegation for now) and an optional\nimpl_cls kwarg on Attention.__init__ so a model can plug in a specialized impl\nwhile reusing the backend's metadata builder. Indexer state lives on the impl.\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n\n* feat(minimax_m3): page-16 constants + fused SHUFFLE KV-insert kernel\n\nTask 1 of the M3 fp8/gluon port. Adds ASM_PAGE_SIZE=16 / PAGES_PER_SPARSE_BLOCK=8\nand grafts the Triton fused Gemma-RMSNorm + partial-NeoX-RoPE + page-16 SHUFFLE\nKV-insert kernel (+ host wrapper) from origin/ganyi/shuffle_kv_cache_fp8_eagle.\nGPU round-trip test validates q_out/index_q_out vs PyTorch ref and K/V/index\ncache scatter at each token slot.\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n\n* feat(minimax_m3): page-16 sparse block-table builders + fused topk EMIT_SPARSE_BT\n\nTask 2 of the M3 fp8/gluon port. Grafts the decode + prefill page-16 sparse\nblock-table builders into sparse_attn.py (each selected logical 128-block expands\nto 8 contiguous physical 16-pages, partial tail packed last, exact context_lens),\nand replaces index_topk.py wholesale with the source-branch version that adds the\nfused EMIT_SPARSE_BT block-table emission and MAX_Q spec-decode causal support\n(both opt-in via defaulted kwargs, so existing decode callers are unaffected).\n\nTests: x8 expansion + tail-last packing + ctx lengths for the standalone builder;\nfused EMIT path matches the standalone builder bit-for-bit (num_kv_heads==1).\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n\n* feat(minimax_m3): gluon PA decode + prefill runners over page-16 SHUFFLE cache\n\nTask 3 of the M3 fp8/gluon port. Grafts minimax_m3_sparse_attn_decode_asm,\nminimax_m3_sparse_attn_prefill_asm, and the shared _run_prefill_fp8_gluon helper\nfrom the source branch: index top-k -> page-16 sparse block table -> AITER gluon\nsplit-KV paged-attention (run_pa_decode_gluon), with fp8 vs bf16 compute_type and\nper-token scales selected by the KV cache dtype. Adds `import aiter` (used for\naiter.dtypes.fp8). Parity test (gluon vs Triton split-K decode reference) for\ngqa 8/16; validated further by the existing asm/fp8/prefill oracle tests.\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n\n* feat(attn): implement SparseMHAPagedAttentionImpl.rope_cache override\n\nTask 4 of the M3 fp8/gluon port. The override runs MiniMax-M3's fused\nqk-norm + partial-NeoX-RoPE + page-16 SHUFFLE KV insert + indexer-key insert via\naiter.fused_qknorm_idxrqknorm (consuming the packed qkv), reading the SHUFFLE\nK/V + scale + index caches off the bound layer. It returns the parent's 7-tuple\n(query rotated) and stashes the rotated indexer query on self._index_q for\ndispatch_backend. fp8 vs bf16 selected by kv_cache_dtype; fp8 writes per-token\ndequant scales into k_scale/v_scale. Adds the _minimax_m3_cos_sin_cache helper.\n\nTest (bf16 + fp8): override returns the 7-tuple, populates _index_q with correct\nshape, and mutates the KV/index caches (+ fp8 scales).\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n\n* feat(attn): implement SparseMHAPagedAttentionImpl.dispatch_backend override\n\nTask 5 of the M3 fp8/gluon port. dispatch_backend returns the M3 sparse\nprefill/decode backend callable (parent contract\nfn(q,k,v,k_cache,v_cache,k_scale,v_scale,fwd_ctx)). Both paths select per-token\ntop-k index blocks with the fused page-16 sparse block-table emit, then run the\ngluon split-KV paged-attention over the SHUFFLE cache; fp8 vs bf16 follows the\ncache dtype inside the runners. Prefill uses the sync-free on-device metadata\nfallback (query_req_id/abs_pos/qo_indptr=None). Consumes self._index_q from\nrope_cache and clears it afterward.\n\nNote: index_cache is page-128 3D [num_logical, 128, idx_head_dim], indexed by the\nlogical block_table in index-topk (distinct from the page-16 SHUFFLE KV cache).\nTest (bf16+fp8): dispatch returns the decode callable; running it yields finite\n[tokens, nh, hd] output and clears _index_q.\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n\n* first version of refactor\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* remove unnecessary files\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* runable and can response resonable output\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* acc right\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* reuse mha's allocation for main cache,  view at use time\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* remove prepare mtp metadata\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* format\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* format\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n* resolve comments\n\nSigned-off-by: ganyi <ygan@amd.com>\n\n---------\n\nSigned-off-by: ganyi <ygan@amd.com>\nCo-authored-by: Claude <noreply@anthropic.com>",
          "timestamp": "2026-06-25T02:16:58Z",
          "url": "https://github.com/feifei14119/ATOM/commit/03a3538243e83fe890d80c7ba2a1a73bc796c00e"
        },
        "date": 1783195034363,
        "tool": "customBiggerIsBetter",
        "benches": [
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc1 request throughput",
            "value": 2276.09,
            "unit": "req/s",
            "extra": "cell=pd-chat-1p1d-conc1 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=409696 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc1 avg latency",
            "value": 0.42,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc1 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=409696 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc1 p99 latency",
            "value": 0.47,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc1 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=409696 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc1 p999 latency",
            "value": 0.52,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc1 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=409696 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc1 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-1p1d-conc1 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=409696 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc16 request throughput",
            "value": 8715.16,
            "unit": "req/s",
            "extra": "cell=pd-chat-1p1d-conc16 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1568729 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc16 avg latency",
            "value": 1.79,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc16 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1568729 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc16 p99 latency",
            "value": 3.32,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc16 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1568729 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc16 p999 latency",
            "value": 4.21,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc16 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1568729 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc16 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-1p1d-conc16 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1568729 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc2 request throughput",
            "value": 3778.87,
            "unit": "req/s",
            "extra": "cell=pd-chat-1p1d-conc2 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=680196 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc2 avg latency",
            "value": 0.5,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc2 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=680196 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc2 p99 latency",
            "value": 0.7,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc2 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=680196 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc2 p999 latency",
            "value": 0.81,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc2 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=680196 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc2 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-1p1d-conc2 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=680196 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc4 request throughput",
            "value": 5740.42,
            "unit": "req/s",
            "extra": "cell=pd-chat-1p1d-conc4 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1033275 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc4 avg latency",
            "value": 0.67,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc4 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1033275 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc4 p99 latency",
            "value": 1.1,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc4 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1033275 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc4 p999 latency",
            "value": 1.39,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc4 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1033275 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc4 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-1p1d-conc4 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1033275 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc8 request throughput",
            "value": 7418.36,
            "unit": "req/s",
            "extra": "cell=pd-chat-1p1d-conc8 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1335304 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc8 avg latency",
            "value": 1.04,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc8 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1335304 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc8 p99 latency",
            "value": 1.9,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc8 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1335304 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc8 p999 latency",
            "value": 2.39,
            "unit": "ms",
            "extra": "cell=pd-chat-1p1d-conc8 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1335304 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-1p1d-conc8 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-1p1d-conc8 router=pd policy=round_robin workers=2 prefill=1 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1335304 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc1 request throughput",
            "value": 2272.4,
            "unit": "req/s",
            "extra": "cell=pd-chat-2p1d-conc1 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=409032 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc1 avg latency",
            "value": 0.42,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc1 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=409032 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc1 p99 latency",
            "value": 0.47,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc1 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=409032 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc1 p999 latency",
            "value": 0.52,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc1 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=409032 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc1 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-2p1d-conc1 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=409032 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc16 request throughput",
            "value": 8666.38,
            "unit": "req/s",
            "extra": "cell=pd-chat-2p1d-conc16 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1559949 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc16 avg latency",
            "value": 1.8,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc16 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1559949 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc16 p99 latency",
            "value": 3.35,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc16 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1559949 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc16 p999 latency",
            "value": 4.26,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc16 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1559949 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc16 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-2p1d-conc16 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1559949 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc2 request throughput",
            "value": 3744.05,
            "unit": "req/s",
            "extra": "cell=pd-chat-2p1d-conc2 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=673929 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc2 avg latency",
            "value": 0.51,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc2 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=673929 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc2 p99 latency",
            "value": 0.7,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc2 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=673929 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc2 p999 latency",
            "value": 0.8,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc2 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=673929 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc2 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-2p1d-conc2 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=673929 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc4 request throughput",
            "value": 5664.56,
            "unit": "req/s",
            "extra": "cell=pd-chat-2p1d-conc4 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1019620 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc4 avg latency",
            "value": 0.67,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc4 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1019620 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc4 p99 latency",
            "value": 1.11,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc4 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1019620 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc4 p999 latency",
            "value": 1.42,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc4 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1019620 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc4 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-2p1d-conc4 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1019620 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc8 request throughput",
            "value": 7376.96,
            "unit": "req/s",
            "extra": "cell=pd-chat-2p1d-conc8 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1327853 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc8 avg latency",
            "value": 1.05,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc8 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1327853 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc8 p99 latency",
            "value": 1.92,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc8 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1327853 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc8 p999 latency",
            "value": 2.41,
            "unit": "ms",
            "extra": "cell=pd-chat-2p1d-conc8 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1327853 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-2p1d-conc8 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-2p1d-conc8 router=pd policy=round_robin workers=3 prefill=2 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1327853 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc1 request throughput",
            "value": 2277.89,
            "unit": "req/s",
            "extra": "cell=pd-chat-3p1d-conc1 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=410020 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc1 avg latency",
            "value": 0.42,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc1 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=410020 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc1 p99 latency",
            "value": 0.47,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc1 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=410020 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc1 p999 latency",
            "value": 0.55,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc1 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=410020 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc1 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-3p1d-conc1 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=1 duration_seconds=180 request_number=410020 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc16 request throughput",
            "value": 8557.26,
            "unit": "req/s",
            "extra": "cell=pd-chat-3p1d-conc16 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1540307 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc16 avg latency",
            "value": 1.82,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc16 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1540307 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc16 p99 latency",
            "value": 3.4,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc16 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1540307 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc16 p999 latency",
            "value": 4.35,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc16 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1540307 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc16 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-3p1d-conc16 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=16 duration_seconds=180 request_number=1540307 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc2 request throughput",
            "value": 3718,
            "unit": "req/s",
            "extra": "cell=pd-chat-3p1d-conc2 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=669240 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc2 avg latency",
            "value": 0.51,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc2 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=669240 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc2 p99 latency",
            "value": 0.71,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc2 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=669240 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc2 p999 latency",
            "value": 0.81,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc2 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=669240 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc2 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-3p1d-conc2 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=2 duration_seconds=180 request_number=669240 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc4 request throughput",
            "value": 5686.88,
            "unit": "req/s",
            "extra": "cell=pd-chat-3p1d-conc4 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1023638 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc4 avg latency",
            "value": 0.67,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc4 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1023638 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc4 p99 latency",
            "value": 1.11,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc4 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1023638 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc4 p999 latency",
            "value": 1.4,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc4 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1023638 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc4 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-3p1d-conc4 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=4 duration_seconds=180 request_number=1023638 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc8 request throughput",
            "value": 7424.11,
            "unit": "req/s",
            "extra": "cell=pd-chat-3p1d-conc8 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1336339 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc8 avg latency",
            "value": 1.04,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc8 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1336339 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc8 p99 latency",
            "value": 1.9,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc8 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1336339 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc8 p999 latency",
            "value": 2.4,
            "unit": "ms",
            "extra": "cell=pd-chat-3p1d-conc8 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1336339 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          },
          {
            "name": "Atomesh-Mocker::pd-chat-3p1d-conc8 failed requests",
            "value": 0,
            "unit": "count",
            "extra": "cell=pd-chat-3p1d-conc8 router=pd policy=round_robin workers=4 prefill=3 decode=1 producers=1 consumers=8 duration_seconds=180 request_number=1336339 Run: https://github.com/feifei14119/ATOM/actions/runs/28716417886"
          }
        ]
      }
    ]
  }
}