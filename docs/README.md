# Docs

These notes tie the videos you referenced to the history of chatbots, models, neural networks, transformers, and training. They also collect resources (papers, repos, videos).

## Contents
- [Rule-based chatbots: from Turing to SmarterChild](./01-rule-based-chatbots.md)
- [Models, neural networks, and training](./02-models-and-neural-networks.md)
- [Transformers, attention, tokens, embeddings, and pretraining/post-training](./03-transformers-attention-and-training.md)
- [ELIZA: the paper, the book, the code, and the effect](./eliza-sources.md) - primary sources, the recovered MIT source, the browser re-implementation, and the ELIZA effect

## Resources

### Papers
- Turing, A. M. (1950). Computing Machinery and Intelligence. *Mind*, 59, 433-460. https://doi.org/10.1093/mind/LIX.236.433 (also text at https://www.csee.umbc.edu/courses/471/papers/turing.pdf)
- Weizenbaum, J. (1966). ELIZA - a computer program for the study of natural language communication between man and machine. *Communications of the ACM*, 9(1), 36-45. https://doi.org/10.1145/365153.365168
- Colby, K. M., Hilf, F. D., Weber, S., & Kraemer, H. C. (1972). Turing-like indistinguishability tests for the validation of a computer simulation of paranoid processes. *Artificial Intelligence*, 3, 199-221. https://doi.org/10.1016/0004-3702(72)90049-5
- Weizenbaum, J. (1967). Contextual Understanding by Computers. *Communications of the ACM*, 10(8), 474-480. https://doi.org/10.1145/363534.363545
- Vaswani, A. et al. (2017). Attention Is All You Need. *NeurIPS*. https://arxiv.org/abs/1706.03762

The rest of the ELIZA trail (SLIP, the MIT Press book *Inventing ELIZA*, the recovered MAD-SLIP source, the MIT archive material, and the ELIZA-effect literature) is collected in [ELIZA: the paper, the book, the code, and the effect](./eliza-sources.md).

### Books/repos (referenced)
- Raschka, S. *Build a Large Language Model (From Scratch)*. https://github.com/rasbt/LLMs-from-scratch (and the "Reasoning from scratch" companion: https://github.com/rasbt/reasoning-from-scratch)
- The Raschka PDFs referenced: https://github.com/ChivuAndrei2003/Build-A-Large-Language-Model-Book---Sebastian-Raschka (includes `Build_a_LLM_from_scratch--BOOK.pdf` and `Build_A_Reasoning_Model_Complete.pdf`)

### Videos (transcripts used)
1. Karpathy, A. "Let's build GPT: from scratch, in code, spelled out." https://youtu.be/kCc8FmEb1nY - bigram baseline → attention → multi-head → residual/LayerNorm → generation, on toy Shakespeare.
2. Karpathy, A. "Deep Dive into LLMs like ChatGPT." https://youtu.be/7xTGNNLPyMI - pretraining data pipeline, tokenization, post-training (SFT/RLHF/RL), hallucination, reward models, verifiable RL.
3. Stanford CS25 "Transformers United" (Winter 2023). https://youtu.be/XfpMkf4rD6E - attention as message passing, causal masking, encoder vs decoder, in-context learning.
4. Ondrej, D. "Fine-tune your own LLM in 13 minutes, here's how." https://youtu.be/g80Q1sVtikE - the fine-tuning workflow (LoRA, 4-bit, data format, export).
5. ByteByteGo. "Transformers Step-by-Step Explained (Attention Is All You Need)." https://youtu.be/avjX3QrYkls - Q/K/V intuition, attention weights, why attention beats recurrence.
6. Syntax. "LLMs Explained: Tokens, Embeddings, Transformers and More." https://youtu.be/YmLp8qe87A0 - tokenization/BPE, embeddings, autoregression, sampling, the context window.

Raw transcript text is not committed; the notes above summarize and cite the sources.

## Notes on this repo
- `api/core/rule/rules.py` is the hand-written rule engine powering the chat UI (no API key, no model provider). What it implements and where it came from: the Rule engine section of `api/README.md`.
- `api/core/rule/` holds the rule-based code; `api/core/nn/` is a placeholder for neural-network/deep-learning code (intended split).
- `api/tests/` is the backend test suite (`cd api && uv run python -m unittest`); conventions are in the Standards section of `api/README.md`.