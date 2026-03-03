import time
import redis
from typing import Tuple, List

class LLMTokenThrottler:
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        # This Lua script runs directly on the Redis server.
        # It calculates how many tokens to add based on time passed,
        # then checks if you have enough for the current LLM request.
        self.lua_script = self.redis.register_script(
            """
            local key = KEYS[1]
            local capacity = tonumber(ARGV[1])
            local refill_rate = tonumber(ARGV[2])
            local requested_tokens = tonumber(ARGV[3])
            local now = tonumber(ARGV[4])

            -- Get current state from Redis
            local bucket = redis.call('HMGET', key, 'tokens', 'last_refreshed')
            local tokens = tonumber(bucket[1])
            local last_refreshed = tonumber(bucket[2])

            -- If this is a new user, fill their bucket to max capacity
            if tokens == nil then
                tokens = capacity
                last_refreshed = now
            end

            -- Calculate how many tokens they earned since their last request
            local time_passed = math.max(0, now - last_refreshed)
            tokens = math.min(capacity, tokens + (time_passed * refill_rate))

            -- Check if they have enough tokens for this LLM prompt
            if tokens >= requested_tokens then
                tokens = tokens - requested_tokens
                redis.call('HMSET', key, 'tokens', tokens, 'last_refreshed', now)
                
                -- Set expiration so old users don't clutter the Redis memory
                local ttl = math.ceil(capacity / refill_rate)
                redis.call('EXPIRE', key, ttl)
                return {1, tokens} -- 1 means Success
            else
                redis.call('HMSET', key, 'tokens', tokens, 'last_refreshed', now)
                return {0, tokens} -- 0 means Rate Limited
            end
            """
        )

    def consume_tokens(self, user_id: str, requested_tokens: int, capacity: int, refill_rate_per_sec: float) -> bool:
        """
        Attempt to consume tokens for an LLM request.
        Returns True if allowed, False if rate limited.
        """
        key = f"llm_rate_limit:{user_id}"
        now = time.time()
        
        # Execute the atomic Lua script in Redis
        result = self.lua_script(
            keys=[key],
            args=[capacity, refill_rate_per_sec, requested_tokens, now]
        )
        
        allowed, remaining_tokens = result[0], result[1]
        
        if allowed:
            print(f" ✅ Allowed. Remaining tokens: {int(remaining_tokens)}")
            return True
        else:
            print(f" ❌ Rate Limited! Need {requested_tokens}, but only have {int(remaining_tokens)}.")
            return False

# --- Example Usage ---
# --- Integration Examples (Multi-Provider) ---
def example_gemini_integration(throttler, user_id, prompt):
    """
    Example: How to estimate tokens for Gemini 
    (Requires google-generativeai package)
    """
    # 1. Count tokens using Gemini's specific tokenizer
    # model = genai.GenerativeModel('gemini-pro')
    # prompt_tokens = model.count_tokens(prompt).total_tokens
    prompt_tokens = len(prompt) // 4  # Rough heuristic for demo
    
    # 2. Add buffer for expected completion (e.g., 1000 tokens)
    total_cost = prompt_tokens + 1000 
    
    if throttler.consume_tokens(user_id, total_cost, 4000, 100):
        print("🟢 Gemini Call Allowed")
        # return model.generate_content(prompt)
    else:
        print("🔴 Gemini Rate Limited")

def example_anthropic_integration(throttler, user_id, prompt):
    """
    Example: How to estimate tokens for Anthropic 
    (Requires anthropic package)
    """
    # 1. Count tokens using Claude's specific tokenizer
    # client = anthropic.Anthropic()
    # prompt_tokens = client.count_tokens(prompt)
    prompt_tokens = len(prompt) // 4  # Rough heuristic for demo
    
    # 2. Add buffer for expected completion
    total_cost = prompt_tokens + 1000
    
    if throttler.consume_tokens(user_id, total_cost, 4000, 100):
        print("🟢 Anthropic Call Allowed")
    else:
        print("🔴 Anthropic Rate Limited")

if __name__ == "__main__":
    # Connect to your Redis instance
    # Defaults to localhost, but in production, use your EC2/ElastiCache endpoint
    try:
        r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        throttler = LLMTokenThrottler(r)

        # Setup: The user can hold a max of 4000 tokens, and regenerates 100 tokens per second.
        MAX_CAPACITY = 4000
        REFILL_RATE = 100

        # Simulating an LLM request that costs 1500 tokens (prompt + expected completion)
        print(f"🚀 Testing Throttler (Capacity: {MAX_CAPACITY}, Refill: {REFILL_RATE}/sec)")
        for i in range(5):
            print(f"Attempt {i+1}: ", end="")
            throttler.consume_tokens("user_123", 1500, MAX_CAPACITY, REFILL_RATE)
            time.sleep(0.5) # Small delay to see refill in action
    except Exception as e:
        print(f"❌ Error connecting to Redis: {e}")
        print("Note: Ensure Redis is running locally or update the connection string.")
