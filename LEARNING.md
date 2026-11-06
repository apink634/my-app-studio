# Conversation evidence

AI-drafted task summary, not a transcript or grade. It may be public. Use actual
short words or labeled paraphrases; disclose help and leave missing responses
pending. The learner reviews, corrects or removes new excerpts before commit/push.
Accuracy approval is not proof of understanding. Label simulated trials explicitly.

**Available conversation context:** APP-001 and APP-002 so far; this session's coach conversation and my own notes.

## APP-001

Available conversation context: this session's chat with the AI coach, plus my own notes file. Quotes are my words with typos fixed.

- Prediction: "theyll probably notice the intended landing screen. this might be like a greeting, or like a get started option, or an intriguing photo."
- Check interpretation: Check shown: the homepage test that requests `/` and looks for my brand name, headline and promise, no "Your Project", one big heading and an SVG logo. In my words: "so this catches bugs that relate to how the page looked before changes were made. it makes sure that the most complete version of the page is being shown"
- Browser observation: "One thing i notice is the big glaring question that is meant to capture user attention. it says zoned out? look at this instead. i wish look was on a new line after out?" (The coach then made the headline break after "Zoned out?".)
- Keep decision: "okay yeah I like it so far." Later: "lets keep it as it is." My idea for an archive of past pieces is parked for a later lesson.
- Review: I reviewed these APP-001 excerpts on Fri Nov 6, 2026, about 9:07 AM Eastern, and told the coach "looks good".
- Help/gaps: The coach drafted the headline and summary text, made the logo mark, wrote the page template and style code, and offered name, archetype and app-idea options; I chose my own idea (a mini art gallery), name (MiniGallery), promise, archetype (Explorer with some Jester), caption and photo, and the link wording "What am I looking at?". Local check gap: one foundation test fails on my Windows laptop because Windows blocks symlink creation without a privilege; I later turned on Developer Mode and the full local check passed. CI was green and PR #2 merged.
- Evidence links / next step: [Issue #1](https://github.com/apink634/my-app-studio/issues/1); [PR #2](https://github.com/apink634/my-app-studio/pull/2), merged.

## APP-002

- Prediction: "The server will tell them that the content is restricted and they do not have access. once they are logged in, it should verify that the user has access and tell them that they have logged in"
- Check interpretation: Check shown: the APP-002 check where a visitor who is not logged in asks for the private dashboard. In my words: "this would catch security bugs for people who are not logged in."
- Browser observation: "it took me to the login page. i made an account. i had to use the guidelines for creating a password since it was too short the first time. it tells me that i am logged in and in the member space. it takes me to the login screen" (the last step was logging out). After my revision: "I see a note for members only added to the dashboard. i like that it says nothing is there yet, it implies more is to come."
- Coach note (not my observation): the server's real behavior for a logged-out visitor is a redirect to the login page, not a "restricted" message.
- Keep decision: I asked for one revision: "i want there to be an actual dashboard when the user logs in instead of just a confirmation they are logged in." I chose a welcome with my username plus a members-only message. Saved pieces are parked. After the revision I said "keep it as is." My prediction "matched exactly" on the behavior.
- Review: I reviewed these APP-002 excerpts on Fri Nov 6, 2026, about 10:15 AM Eastern, and told the coach "looks good".
- Help/gaps: The coach wrote the accounts code, the three page templates and the style code, and drafted the members-only wording (which I can rewrite). I chose the expected behavior, the dashboard contents and the revision, and tested the pages myself. Local check gap: none; the full check passed on my laptop.
- Evidence links / next step: [Issue #3](https://github.com/apink634/my-app-studio/issues/3); [PR #4](https://github.com/apink634/my-app-studio/pull/4). Merged with CI green. Next: APP-003.

## APP-003

- Prediction: "the server would check if the account is registered as an admin."
- Check interpretation: Check shown: a logged-in member requests `/api/admin` directly and gets 403. In my words: "It would catch a security bug since it makes sure only authorised users have access to sensitive pages."
- Browser observation: As a member: "it says: admin access required and tells me that i am logged in as ann". After the trusted terminal command made me an admin and I refreshed: "now it shows me the administration page and says only curator can see the page".
- Coach note (not my observation): the server answers 401 to anonymous visitors, 403 to members and 200 to admins, and it reads my role from the database on every request, so the change showed up without logging in again.
- Keep decision: "lets keep this as it is, i like that it shows the username of who you are logged in as so you know whether or not is the right account for admin access. i still want to add the features for admins to be able to add photos later" (parked for a later scope).
- Review: I reviewed these APP-003 excerpts on Fri Nov 6, 2026, about 11:06 AM Eastern, and told the coach "looks good".
- Help/gaps: The coach wrote the admin route and page and explained the role command. I chose the admin page wording ("Only the curator of the gallery can see this page"), ran the role command myself, tested the member and admin views in my browser, and decided to keep it. Local check gap: none; the full check passed on my laptop.
- Evidence links / next step: [Issue #6](https://github.com/apink634/my-app-studio/issues/6); PR link in SPEC.md once opened. Next: PR, CI, merge, then submit.
