
- setting Accent for the audio
- [x] show transcript in align by audio cursor
- [x] If the level is higher than B1, then we don't need the native language, all the podcast script must be in learning language
- [x] generate interactive exercise at end of the podcast, the exercises must be in following categories: 1 speaking exercise about the topic, 2 exercise about the meaning of the hard words that disussed in the podcast and 2 exercise about multi-choice reading. At end evaluate the answer by givings score from 1 to 10 and feadback review like a teacher.
- [x] user able to set the length of the podcast
- [*] saved the described words in the listened podcast in db table and use it in the next podcast generation loop to avoid describing again. you can create mcp for this table and use it in the multi-agent architecture
- user can change the speed of the audio playing
- calculate token consumption and time for generating in each podcast. and store it in the db and show it the end of the podcast  page.
- [x]for researching topic add limit of 10
tech debts:
- [x] create mcp for the topic retrieval API
- [x] set step budget for the agent loop