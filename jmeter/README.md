# JMeter Load Tests

The plan `yelp-load-test.jmx` exercises the three endpoints the Lab 2 spec
asks you to measure:

1. `POST /api/v1/auth/login`
2. `GET  /api/v1/restaurants` (search)
3. `POST /api/v1/restaurants/{id}/reviews` (triggers Kafka flow)

## Before you run it

1. Bring the stack up with `docker compose up -d`.
2. Seed Mongo so the search returns rows:
   ```bash
   docker compose exec restaurant-api python seed_mongo.py
   ```
3. Create a test user (JMeter will sign in as it — not sign up):
   ```bash
   curl -X POST http://localhost:8080/api/v1/auth/signup \
     -H 'Content-Type: application/json' \
     -d '{"name":"Load Test","email":"loadtest@example.com","password":"Password123"}'
   ```

## Running headless at each concurrency level

The plan takes `-J` CLI properties. Example for 100 users:

```bash
jmeter -n -t jmeter/yelp-load-test.jmx \
  -Jhost=localhost -Jport=8080 \
  -Jusers=100 -Jrampup=30 -Jloops=5 \
  -Jemail=loadtest@example.com -Jpassword=Password123 \
  -l results/run-100.jtl -e -o results/run-100-report
```

Repeat with `-Jusers=200`, `300`, `400`, `500`. The HTML report in
`results/run-<n>-report/` has per-sample average response time and
throughput — pull those numbers into your report's graph.
