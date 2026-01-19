# RPC Endpoint Options for Polygon

If you're experiencing rate limit errors, consider using a different RPC endpoint.

## Free Public Endpoints

### Polygon Mainnet

1. **Polygon RPC (Official)**
   ```
   https://polygon-rpc.com
   ```
   - Free, but has rate limits
   - Good for testing

2. **Alchemy (Free Tier)**
   ```
   https://polygon-mainnet.g.alchemy.com/v2/YOUR_API_KEY
   ```
   - Sign up at: https://www.alchemy.com/
   - Free tier: 300M compute units/month
   - More reliable than public endpoints

3. **Infura (Free Tier)**
   ```
   https://polygon-mainnet.infura.io/v3/YOUR_PROJECT_ID
   ```
   - Sign up at: https://infura.io/
   - Free tier: 100k requests/day
   - Reliable and fast

4. **QuickNode (Free Tier)**
   ```
   https://your-endpoint.quiknode.pro/YOUR_API_KEY
   ```
   - Sign up at: https://www.quicknode.com/
   - Free tier available

5. **PublicNode**
   ```
   https://polygon.publicnode.com
   ```
   - Free public endpoint
   - No API key required

## How to Update Your .env File

1. Choose an endpoint from above
2. If it requires an API key, sign up and get your key
3. Update your `.env` file:

```env
# For public endpoints (no key needed)
RPC_URL=https://polygon-rpc.com

# For Alchemy (with API key)
RPC_URL=https://polygon-mainnet.g.alchemy.com/v2/YOUR_API_KEY

# For Infura (with project ID)
RPC_URL=https://polygon-mainnet.infura.io/v3/YOUR_PROJECT_ID
```

## Rate Limit Handling

The script now includes automatic retry logic:
- If you hit a rate limit, it will wait and retry automatically
- Default retry time is extracted from the error message (usually 10 seconds)
- Maximum 5 retries before giving up

## Recommended Setup

For production use, we recommend:
1. **Alchemy** or **Infura** (free tier is usually sufficient)
2. Sign up and get your API key
3. Update `RPC_URL` in your `.env` file

This will give you much better reliability than public endpoints.
