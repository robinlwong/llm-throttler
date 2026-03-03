# Standalone Redis LLM Token Throttler

![Redis](https://img.shields.io/badge/redis-%23DD0031.svg?style=for-the-badge&logo=redis&logoColor=white)
![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![Lua](https://img.shields.io/badge/lua-%232C2D72.svg?style=for-the-badge&logo=lua&logoColor=white)

A standalone, atomic, cost-aware LLM rate limiter designed to protect multi-agent AI ecosystems from hitting API quotas.

## 🏆 Why Redis is the Superior Choice for LLM Throttling

When managing a high-concurrency ecosystem of agentic AIs, choosing Redis over standard cloud offerings (like AWS WAF or API Gateway) isn't just a preference—it's an architectural necessity for the following reasons:

### 1. Atomic Lua Scripting (Zero Race Conditions)
In multi-agent environments, several agents often hit the LLM gateway at the exact same millisecond. 
- **The Competitor Fail:** Traditional databases or AWS WAF often use a "Read-Modify-Write" pattern which is prone to race conditions. Two agents might both see "100 tokens left," both consume 100, and leave you at -100 (Quota Exceeded).
- **The Redis Win:** By using **Lua scripts**, the entire "Check-and-Deduct" operation is executed **atomically** on the Redis server. Redis treats the Lua script as a single command, locking out other requests until the math is done. This guarantees that your token count is always 100% accurate, even during massive traffic bursts.

### 2. Sub-Millisecond Latency (In-Memory Speed)
Throttling is an overhead task; it must be faster than the primary task.
- **The Comparison:** Standard API Gateways or databases incur disk I/O or complex network routing overhead. 
- **The Redis Win:** As an in-memory data store, Redis handles these bucket checks in **sub-millisecond time**. This ensures that adding a safety layer to your agents doesn't introduce a perceptible lag in their response time.

### 3. State Continuity Across Agents
Your agents are likely distributed across different containers, servers, or even AWS regions.
- **The Benefit:** Redis acts as the **"Single Source of Truth."** It doesn't matter if Agent A is in one city and Agent B is in another; as long as they point to the same Redis instance, they share the same token pool. This prevents "Limit Leaks" that happen when rate-limiting is handled locally within individual agent code.

### 4. Dynamic TTL & Memory Efficiency
Redis handles data expiration natively via the `EXPIRE` command.
- **The Benefit:** In the `Token Bucket` implementation, we set a TTL based on the refill rate. If a user or agent stops making requests, their rate-limit data **automatically evaporates** from Redis. This prevents your "Token Bank" from growing into a massive database of inactive users.

### 5. Cost-Awareness (RPM vs. TPM)
Most managed services limit by **Requests** (RPM). LLMs limit by **Tokens** (TPM).
- **The Core Advantage:** Redis allows us to implement **Variable Costing**. We can charge an agent 1,000 tokens for a complex "Reasoning" task and only 50 tokens for a "Greeting" task. Standard cloud tools simply cannot differentiate between the two, making them blunt instruments for the surgical precision required in LLM management.

---

## ⚠️ Disclaimer

This software is provided for educational and research purposes only. The authors, contributors, and Seqquant LLC are not responsible for any costs, API overages, financial losses, or service disruptions incurred through the use of this tool. Use at your own risk.

---

## 🤖 Multi-Model Strategy: Anthropic vs. Gemini

**Is it advisable to have separate code?**
No, you should **not** have separate throttler logic for different models. You want a **Unified Throttling Core** with a **Provider-Specific Adapter**.

### The Best Implementation Pattern: "The Wrapper"
The core Lua logic (the "Bucket") stays the same. The difference lies in how you **count** the tokens before asking Redis for permission.

1.  **Anthropic:** Uses the `anthropic` Python SDK's `count_tokens` or the `tokenizers` library (Claude uses a specific Byte-Pair Encoding).
2.  **Gemini:** Uses the `google-generativeai` SDK's `count_tokens` method (Gemini's encoding differs slightly from OpenAI/Anthropic).

### Recommended Architecture:
```python
class UnifiedLLMManager:
    def execute(self, provider, prompt):
        # 1. Get count from provider-specific tokenizer
        token_count = provider.get_token_count(prompt)
        
        # 2. Ask the SAME Redis Throttler for permission
        if throttler.consume_tokens(user_id, token_count):
            return provider.call_api(prompt)
        else:
            raise RateLimitError()
```
*This ensures your "Total Token Budget" is managed in one central place, even if you are load-balancing between Claude and Gemini.*

## 🛠️ Setup
1. `pip install redis`
2. Configure your Redis endpoint in `redis_throttler.py`.
3. Run the throttler.
