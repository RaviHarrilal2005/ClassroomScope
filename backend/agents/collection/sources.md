# ClassroomScope - News Sources

## RSS Feeds (6)

1. **The Hechinger Report** - https://hechingerreport.org/
- Topics: Education, innovation, policy
- Notes: Looks for AI/edtech articles

2. **Inside Higher Ed** - https://www.insidehighered.com/
- Topics: Higher education, faculty, administration
- Notes: Strong coverage of AI in college settings

3. **EdSurge** - https://www.edsurge.com/
- Topics: Research, technology, education resources
- Notes: Focuses on education technology

4. **Higher Ed Dive** - https://www.highereddive.com/
- Topics: Policies, leadership, enrollment
- Notes: College-oriented discussions

5. **eSchool News** - https://www.eschoolnews.com/
- Topics: Education innovations, insights, resources
- Notes: Centers on teaching, leadership, well-being

6. **The Conversation** - https://theconversation.com/
- Topics: Academic rigor, journalism, analysis
- Notes: Dedicated coverage on AI and Education

7. **The Chronicle of Higher Education** - https://www.chronicle.com/
- Topics: intelligence, career development, innovate
- Notes: Empower with insight the world of higher education

8. **Tech & Learning** - https://www.techlearning.com/
- Topics: Improvement, leadership, technology
- Notes: Written effective implementations for education improvements

## News APIs (3)

1. **NewsAPI** - https://newsapi.org/
- Endpoint: `/v2/everything?q=generative%20AI%20education`
- Free tier: 100 requests/day
- API Key: stored in .env as `NEWS_API_KEY`

2. **GNews API** - https://gnews.io/
- Endpoint: `/search?q=generative%20AI%20education`
- Free tier: 100 requests/day
- API Key: stored in .env as `GNEWS_API_KEY`

3. **The Guardian Open Platform** - https://open-platform.theguardian.com/
- Endpoint: `https://content.guardianapis.com/search`
- Free tier: Developer tier, ~1 req/sec, 500 calls/day
- API Key: stored in .env as `GUARDIAN_API_KEY`
- Notes: Unlike the other sources, Guardian articles carry a
  `commentable` flag and a short URL (`/p/xxxxx`) that maps to a
  Discussion API endpoint for comment retrieval. See
  `guardian_fetcher.py` and `guardian_comments.py`.
- Discussion API (undocumented, separate from Open Platform):
  `https://discussion.theguardian.com/discussion-api/discussion//p/<shortid>`
  — no auth, paginates top-level comments, replies embedded.

## Additional Notes
- All sources are English-language news articles
- Focus on Generative AI, ChatGPT, and AI policy in education

