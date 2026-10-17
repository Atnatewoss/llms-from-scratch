# ELIZA: the paper, the book, the code, and the effect

Companion to [01-rule-based-chatbots.md](./01-rule-based-chatbots.md). That file puts rule-based chatbots in a timeline; this one is the source list behind the ELIZA entry - the primary papers, the MIT Press book, the recovered MAD-SLIP code, the browser re-implementation, and the psychology of the "ELIZA effect".

Nothing here is used by the rule engine. The engine is hand-written (see `api/core/rule/rules.py`); these are the readings.

## What ELIZA actually was

- **ELIZA is the program; DOCTOR is one script.** ELIZA is a general conversational agent that interprets a separate, domain-specific script. The famous Rogerian-therapist behaviour comes from the DOCTOR script, which is why "ELIZA" has come to mean "ELIZA running DOCTOR". Weizenbaum's own framing (1967): "From one point of view, an ELIZA script is a program and ELIZA itself an interpreter. From another perspective, ELIZA appears as an actor who must depend on a script for his lines."
- **Written in MAD-SLIP, not Lisp.** MAD ("Michigan Algorithm Decoder", Algol-like) plus Weizenbaum's SLIP list-processing extension, running on MIT's Compatible Time-Sharing System (CTSS) on an IBM 7094, developed 1964-1967. Roughly 420 lines; the main program is about 230.
- **Named after Eliza Doolittle** (*Pygmalion* / *My Fair Lady*): a system that could be "taught to speak increasingly well".
- **At least five major versions between 1965 and 1968**, with scripts well beyond DOCTOR (arithmetic tutoring, a Nixon parody).
- **The 1966 paper published the DOCTOR script, not the code.** The algorithm was described in detail; the ~420 lines of MAD-SLIP stayed lost for 55 years. The dialogue printed in the paper was almost certainly constructed or heavily cleaned up rather than captured live.
- **The "ELIZA was Lisp" myth** came from Bernie Cosell writing a Lisp version straight from the 1966 paper shortly after publication. He never saw the original.

## How DOCTOR worked

- **Five technical problems** Weizenbaum set out to solve: identifying key words, finding a minimal context, choosing transformations, generating a response when there are no key words, and letting scripts be edited.
- **Keywords with a RANK** (precedence) are collected into a "keystack"; the highest-ranked keyword's rule wins. The input is then split by a **decomposition rule** and rebuilt by an **assembly (reassembly) rule**. His own example: "You are very helpful" → reflected → "What makes you think I am very helpful?"
- **Equivalence classes and a fake keyword.** DOCTOR's `DIT` is not an English word - it is a collecting point for one set of likeness replies. Three near-synonyms own no replies at all and just point at it:

  ```lisp
  (DIT   ((0) (IN WHAT WAY) (WHAT RESEMBLANCE DO YOU SEE) (HOW)))
  (ALIKE 10 (=DIT))
  (SAME  10 (=DIT))
  (LIKE  10 (=DIT))
  ```

  So "Men are all alike" matches `ALIKE`, defers to `DIT`, and answers **"IN WHAT WAY"** - the first line of the famous 1966 dialogue. The `=` is how the script builds equivalence classes without repeating text. It also gives the trick away: a keyword match pours your own words into a shared template.
- **When nothing matches:** either a content-free prompt ("I see", "Please go on") or the **MEMORY** queue - an earlier user sentence, reflected back. In the recovered code the "counting mechanism" the paper is vague about is `LIMIT`, cycling 1→4 and then restarting; at `LIMIT = 4` with no keyword match it pops the oldest stored memory.
- **Reading the recovered code** needs two vocabularies. MAD-SLIP keywords: `W'R` = whenever/if, `O'E` = otherwise/else, `E'L` = end of conditional, `T'O` = transfer to (goto), `T'H <a> THROUGH <b>` = loop to label, `F'N <v>` / `E'N` = function return / end of function. Booleans read like Fortran: `.E.` equal, `.NE.` not equal, `.L.`/`.LE.` less/less-or-equal, `.G.`/`.GE.` greater/greater-or-equal. `$…$` delimits string constants.
- **The engine in this repo is the same idea with the knobs changed.** Instead of keyword ranks and decomposition/assembly rules, `api/core/rule/rules.py` uses ordered groups of regex patterns with template replies; the `eliza` group and the `statements` pool carry DOCTOR's reflections ("Why do you feel X?", "Please go on."). Ordered matching is the shared mechanism.

## The browser re-implementation (elizaemulator.com)

A small JavaScript rebuild that is explicitly "faithful in spirit, modern in format", not a byte-for-byte recreation. Useful because it documents the minimal pipeline in plain language:

1. **Normalise** the input (trim, lowercase, simplify punctuation).
2. **Check ordered rules** for strong patterns - feelings, family, beliefs, reasons.
3. **Capture a phrase** from the sentence if the rule needs one.
4. **Apply reflections** so "I", "my", "you are" shift into the bot's perspective.
5. **Choose a response template** and insert the captured phrase.
6. **Fall back gracefully** with stock prompts.

Worked example: "I feel anxious today." matches the *feelings* rule, captures "anxious today", and fills the template `Do you often feel (1)?`. The reflection map is small:

```js
const reflections = {
  "i am": "you are",
  "i": "you",
  "my": "your",
  "you are": "I am",
  "you": "I",
};
```

Its rule topics: feelings ("I feel…", "I am feeling…"), family (mother, father, parents, sister, brother, partner), beliefs ("I think…", "I believe…"), reasons ("because…"), difficulties ("I can't…"), wants and needs ("I want…", "I need…"), dreams (dream/dreamt/dreamed), absolutes and tension (always/never), deflection toward the bot ("you…"), simple yes/no handling, and a generic fallback. The site also hosts a comic-bureaucrat persona (**Humphrey**) and a comparison of ELIZA against **text-adventure parsers** - two early typed-language interfaces that use the same input box for very different jobs (conversation vs. command).

Two limits it names itself, which match this repo's engine: it can repeat itself, and it has no wider context.

## The ELIZA effect

- **Definition:** the tendency to read far more understanding, empathy, memory, or intention into a computer system than it has. In Hofstadter's formulation, "the susceptibility of people to read far more understanding than is warranted into strings of symbols - especially words - strung together by computers".
- **Where the term comes from:** Hofstadter, *Preface 4: The Ineradicable Eliza Effect and Its Dangers*, in *Fluid Concepts and Creative Analogies* (Basic Books, 1995), p. 157 - his example is an ATM saying "THANK YOU". Sherry Turkle popularised the term (*The Second Self*, 1984, p. 40).
- **Weizenbaum's reaction** is the historically important part. After users confided in ELIZA he wrote: "I had not realized … that extremely short exposures to a relatively simple computer program could induce powerful delusional thinking in quite normal people" (*Computer Power and Human Reason*, 1976, p. 7). The best-known anecdote - his secretary asking him to leave the room so she could talk to ELIZA privately - is reported in several wordings, and recent scholarship treats it cautiously. It pushed him from building AI to criticising it: he chose the psychotherapy frame precisely to "sidestep the problem of giving the program a data base of real-world knowledge", and then spent the rest of his career arguing that some thought should stay human.
- **Mechanisms usually listed:** anthropomorphism, reciprocity (a system replies, so we reply), the coherence illusion (a few plausible turns imply depth), emotional projection (calm wording reads as care), and role expectation (a therapist persona is judged differently from a search box).
- **The pushback:** Noah Wardrip-Fruin argues the illusion is paper-thin and that sustained interaction usually turns into *play* - users either try to make the bot say something absurd or work to keep it coherent. Turkle observed the same thing: many users avoided questions they knew would "confuse" the program, to maintain the illusion.
- **Why it matters now:** fluency is not understanding. The more coherent and responsive a system sounds, the easier it is to overestimate what it knows, remembers, intends, or should be trusted with. Judge a conversational system by its capabilities and limits, not its tone.

The equivalent disclosure in this repo is deliberate: when it does not know something the bot says so plainly, `capabilities` lists exactly what it can do, and unmatched input is answered with an honest shrug instead of invention.

## The recovered source (MIT, 2021)

- **2021:** Jeff Shrager, guided by MIT Libraries archivist Myles Crowley, searched Weizenbaum's papers in the MIT archive. A folder labelled "Computer Conversations" held a complete MAD-SLIP source listing of ELIZA with the DOCTOR script attached - the first sighting in over fifty years. Weizenbaum's estate released it under a **CC0 public-domain** licence; Anthony Hay transcribed, translated, and annotated the core code.
- **December 2024:** Rupert Lane, on a CTSS / IBM 7094 emulator built by David Pitts, brought the original up again - roughly **96% of the 1965 functions** - and reproduced the conversations published in the 1966 paper almost exactly.
- **Why the recovery changed the story:** the recovered code shows a general conversational system assembled incrementally, not just the DOCTOR demo - the basis for the *Inventing ELIZA* book.

## Beyond the 1960s: the chatbot lineage

Timeline entries that extend the one in [01-rule-based-chatbots.md](./01-rule-based-chatbots.md):

- **1988 - Jabberwacky** (Rollo Carpenter): moves past rigid rules by learning from interactions; intelligence as accumulated conversation rather than predefined logic.
- **1992 - Dr. Sbaitso** (Creative Labs): a DOCTOR-style character shipped with Sound Blaster cards; early voice interaction, and a very widely heard echo of ELIZA.
- **2006 - IBM Watson**; **2008 - Google Talkbot**: question answering and bots inside communication platforms.
- **2010 - Siri**; **2011 - Watson wins *Jeopardy!***; **2014 - Eugene Goostman** revives the Turing-test debate; **2015 - Facebook Messenger Platform** opens a bot ecosystem; **2016 - Microsoft Tay** shows a bot mirroring its users, and **Google Assistant** makes assistants ambient.
- **2020 - GPT-3**; **2022 - ChatGPT**; **2023 - GPT-4**: the move from a tool people use to something they think with. A 2023 preprint reported that ELIZA - the 1966 script - still fooled more judges than GPT-3.5 in a Turing-test study, though not GPT-4 or real humans.

## Where to read it

### The book
- Ciston, S., Berry, D. M., Hay, A., Marino, M. C., Millican, P., Schwarz, A., Shrager, J., & Weil, P. (2026). *Inventing ELIZA: How the First Chatbot Shaped the Future of AI.* MIT Press (Software Studies). ISBN 978-0-262-05248-1. **Open access:** https://direct.mit.edu/books/oa-monograph/6171/Inventing-ELIZAHow-the-First-Chatbot-Shaped-the · https://mitpress.mit.edu/9780262052481/inventing-eliza/ · project site: https://findingeliza.org
  Critical-code-studies reading of the rediscovered code, with missing scripts and archival research at MIT, Stanford, and UCLA. Its companion site includes a faithful in-browser recreation of the first chatbot and a keyword-by-keyword view of the DOCTOR dictionary.
- Weizenbaum, J. (1976). *Computer Power and Human Reason: From Judgment to Calculation.* W. H. Freeman. ISBN 0-7167-0464-1 (Penguin ed. 1984). The book he wrote in reaction to how people treated ELIZA; the source of the "delusional thinking" quote.

### The papers
- Weizenbaum, J. (1966). ELIZA - A Computer Program for the Study of Natural Language Communication Between Man and Machine. *CACM* 9(1), 36-45. https://doi.org/10.1145/365153.365168 - the paper; the DOCTOR script is its appendix.
- Weizenbaum, J. (1967). Contextual Understanding by Computers. *CACM* 10(8), 474-480. https://doi.org/10.1145/363534.363545 - the scripts-as-programs framing.
- Weizenbaum, J. (1963). Symmetric List Processor. *CACM* 6(9), 524-536. https://doi.org/10.1145/367593.367617 - SLIP, the list layer ELIZA was built on.
- Colby, K. M., Watt, J. B., & Gilbert, J. P. (1966). A Computer Method of Psychotherapy. *J. Nervous and Mental Disease* 142(2), 148-152. https://pubmed.ncbi.nlm.nih.gov/5936301/
- Quarton, G. C., McGuire, M. T., & Lorch, S. (1967). Man-machine natural language exchanges based on selected features of unrestricted input, I & II. *J. Psychiatric Research* 5(2), 165-177. https://pubmed.ncbi.nlm.nih.gov/6056818/ - the dyadic-communication experiments that used ELIZA with real subjects.
- Eisenmann, C., Mlynář, J., Turowetz, J., & Rawls, A. W. (2023). "Machine Down": making sense of human-computer interaction - Garfinkel's research on ELIZA and LYRIC from 1967 to 1969. *AI & Society*. https://doi.org/10.1007/s00146-023-01793-z - includes transcripts of real people talking to ELIZA.
- Shah, H., Warwick, K., Vallverdú, J., & Wu, D. (2016). Can machines talk? Comparison of Eliza with modern dialogue systems. *Computers in Human Behavior* 58, 278-295. https://doi.org/10.1016/j.chb.2016.01.004
- Jones, C. R., & Bergen, B. K. (2023). Does GPT-4 pass the Turing test? https://arxiv.org/abs/2310.20216 - the preprint in which 1966 ELIZA out-fooled GPT-3.5.

### The ELIZA effect
- Hofstadter, D. R. (1995). *Fluid Concepts and Creative Analogies*, "Preface 4: The Ineradicable Eliza Effect and Its Dangers", p. 157. Basic Books.
- Turkle, S. (1984). *The Second Self: Computers and the Human Spirit*, p. 40. Simon & Schuster.
- Berry, D. M. (2023). The Limits of Computation: Joseph Weizenbaum and the ELIZA Chatbot. *Weizenbaum Journal of the Digital Society* 3(3). https://doi.org/10.34669/WI.WJDS/3.3.2 (open access)
- Dillon, S. (2020). The Eliza effect and its dangers: from demystification to gender critique. *Journal for Cultural Research* 24(1), 1-15. https://doi.org/10.1080/14797585.2020.1754642
- Bassett, C. (2019). The computational therapeutic: exploring Weizenbaum's ELIZA as a history of the present. *AI & Society* 34(4), 803-812. https://doi.org/10.1007/s00146-018-0825-9
- Wardrip-Fruin, N. (2009). *Expressive Processing*, p. 33. MIT Press - the "it becomes play" argument.
- Marino, M. C., & Berry, D. M. (2024). Reading ELIZA: Critical Code Studies in Action. *Electronic Book Review*. https://electronicbookreview.com/essay/reading-eliza-critical-code-studies-in-action/

### MIT and archives
- The recovered source and its commentary: https://elizagen.org (curated by Jeff Shrager) - see *Original ELIZA* for the MAD-SLIP listing, transcriptions, the CC0 release, and the MAD-SLIP key; *Resources* for the paper list.
- Hayward (1967), *Flexible discussion under student control in the ELIZA computer program*, MIT bachelor's thesis. https://dspace.mit.edu/handle/1721.1/142746 (MIT DSpace)
- Hayward, P. R. (1968). *ELIZA Scriptwriter's Manual.* Computer History Museum. https://archive.computerhistory.org/resources/access/text/2022/04/102683842-05-01-acc.pdf - the MIT education branch of ELIZA.
- CTSS MAD manual (MIT): https://people.csail.mit.edu/saltzer/CTSS/CTSS-Documents/MAD-manual.pdf · MAD-SLIP manual, extracted from the IBM 7090 user's guide: https://drive.google.com/file/d/1XtF7EM1KhwMPKsp5t6F0gwN-8LsNDPOl/view
- FORTRAN Assembly Program (FAP) for the IBM 709/7090, Computer History Museum: https://www.computerhistory.org/collections/catalog/102663110
- Computer History Museum, *The Promise of the DOCTOR Program: Early AI at Stanford*: https://computerhistory.org/blog/the-promise-of-the-doctor-program-early-ai-at-stanford/
- CoRecursive podcast, "ELIZA with Jeff Shrager": https://corecursive.com/eliza-with-jeff-shrager/

### Code to read
- Anthony Hay's near-perfect C++ clone of the original MAD-SLIP ELIZA (written from the 1966 paper, corrected against the recovered source): https://github.com/anthay/ELIZA
- The archaeology project's own repository: https://github.com/critical-code-studies/ELIZA
- GNU Emacs ships a DOCTOR-style ELIZA: `M-x doctor`.
- Jeff Shrager's BASIC clone (1973; printed in *Creative Computing*, 1977) is the ancestor of a large branch of hobbyist ELIZA ports.

### Explainers and articles
- ELIZA Emulator (try it, plus the how-it-works pipeline, rule topics, reflection map, and an ELIZA-effect page): https://elizaemulator.com · https://elizaemulator.com/how-it-works · https://elizaemulator.com/eliza-effect
- London Intercultural Academy, *The Story of ELIZA: The AI That Fooled the World* (history-decade framing and the three-reason explanation of the effect): https://liacademy.co.uk/the-story-of-eliza-the-ai-that-fooled-the-world/
- Wikipedia, *ELIZA* and *ELIZA effect* - useful as a citation trail into the primary literature rather than as a source in itself.
