# Transformers, attention, tokens, embeddings, and pretraining/post-training

## From RNNs to Transformers (why attention)
Before transformers, sequence models used RNNs/LSTMs that processed tokens one by one, updating hidden state. That gave sequential processing (slow, hard to parallelize) and struggled with long-range dependencies ("I grew up in France… I speak fluent ___"). (ByteByteGo; CS25)

The 2017 paper **"Attention Is All You Need" (Vaswani et al.)** showed you could remove recurrence and rely on self-attention plus MLPs. Key points:
- **Attention lets every token talk to every other token** at once, regardless of distance. (ByteByteGo)
- **GPU-friendly parallelism**: matrix form makes it efficient on modern hardware. (ByteByteGo; Karpathy GPT)
- **Domain general**: works for text, images (ViT), audio (Whisper), etc. (CS25)
- **Architecture survives**: residual connections, layer norms, multi-head attention, positional encodings, MLP blocks remain central. (CS25; Karpathy GPT)

## What is attention?
At its core, attention is a data-dependent weighted sum of values. For each token:
- **Query (Q)**: "what am I looking for?"
- **Key (K)**: "what do I contain?"
- **Value (V)**: "what content do I share?"

Steps (matrix form):
1. Project each token embedding into Q,K,V via learned linear maps.
2. Compute affinities: `score = Q @ K^T` (how much token i attends to token j).
3. Scale by `1/√head_size` to keep variance stable (prevents softmax from saturating).
4. Apply causal mask (for decoder-only models) by setting future positions to -∞ so the model can't see the future.
5. Normalize with softmax to get attention weights (sum to 1 per query).
6. Compute weighted sum: `output = weights @ V` - each token becomes a context-aware blend of all (allowed) tokens' values.

This is done in parallel across all tokens. (ByteByteGo; Karpathy GPT; CS25)

## Multi-head attention and the transformer block
- **Multi-head attention**: run several attention heads in parallel with different Q/K/V weights; concatenate results. Each head can learn different relationships (syntax, coreference, etc.). (ByteByteGo; Karpathy GPT)
- **Transformer block**: typically interleaves `multi-head self-attention` (communication: tokens exchange info) and `feed-forward MLP` (computation: each token refines itself). (CS25)
- **Residual connections** (skip connections): add input back to output (`x + sublayer(x)`) to help gradient flow ("gradient super highway"). (Karpathy GPT; CS25)
- **LayerNorm**: normalize each token's features to zero mean/unit variance (pre-norm variant is common now). (Karpathy GPT; CS25)
- **Stacking**: dozens/hundreds of blocks build up increasingly abstract representations. (Syntax)

## Tokenization details
- **Goal**: map text to integers (token IDs). Subword tokenization (BPE) balances vocabulary size vs sequence length. (Syntax; Karpathy Deep Dive)
- **BPE process**: start from characters/bytes, repeatedly merge most frequent adjacent pairs until target vocab size is reached; merges don't cross word boundaries in typical implementations. (Syntax)
- **Tradeoffs**: smaller vocab → longer sequences; larger vocab → shorter sequences but more parameters in embedding tables. (Syntax; Karpathy GPT)
- **Vocabulary IDs are arbitrary** - they carry no intrinsic meaning; meaning comes from embeddings and training. (Syntax)

## Embeddings and positional encodings
- **Token embeddings**: learned lookup table `vocab_size × d_model` mapping each token ID to a dense vector. (Karpathy GPT; Syntax)
- **Meaning from context**: embeddings end up reflecting co-occurrence patterns (distributional semantics). (Syntax)
- **Positional encodings/embeddings**: added to token embeddings so the model knows order (since attention is permutation-invariant over a set). (ByteByteGo; CS25; Karpathy GPT)
- **Dimensions**: embedding dimension `d_model` is the width of vectors flowing through the network (e.g., 32 toy → 12k+ large). (Syntax; Karpathy GPT)

## Pretraining (next-token prediction)
- **Corpus**: large cleaned text (filtered/deduped Common Crawl-derived datasets like FineWeb). (Karpathy Deep Dive)
- **Training objective**: maximize probability of the true next token given context → minimize cross-entropy loss. (Karpathy GPT)
- **Data shapes**: batches of `(batch_size, block_size)` windows; targets are shifted by 1. (Karpathy GPT)
- **Optimizer**: Adam/AdamW with learning rate scheduling. (Karpathy GPT)
- **Base model result**: after pretraining, you get a decoder-only base model that is a strong next-token predictor (internet document completer), not necessarily a conversational assistant. (Karpathy Deep Dive)

## Post-training: fine-tuning, alignment, RLHF
- **Supervised Fine-Tuning (SFT)**: continue training on curated conversation pairs (user/assistant) in a standard format (ChatML/ShareGPT). Same objective, different data distribution. (Karpathy Deep Dive; Ondrej)
- **LoRA adapters**: train only low-rank additions to weight matrices - efficient, uses less memory, easy to swap. (Ondrej)
- **Quantization (4-bit)**: reduces memory footprint to run smaller models on consumer GPUs. (Ondrej)
- **RLHF**: train a reward model on human rankings of outputs, then use RL (e.g., PPO) to optimize the policy against that reward. Helps align behavior to preferences. (Karpathy Deep Dive)
- **RL on verifiable tasks**: for math/coding with checkable answers, RL can reinforce correct solutions and allow emergent reasoning traces ("thinking" models). (Karpathy Deep Dive)
- **Caution**: reward models can be gamed; RLHF is typically used with care and early stopping in practice. (Karpathy Deep Dive)

## Inference and serving (practical notes)
- **Autoregressive loop**: sample one token at a time from `softmax(logits / temperature)` (optionally with `top-p/top-k`), append to context, repeat until stop token or max length. (Syntax; Karpathy GPT)
- **Context is the memory**: the full conversation history is included in each request (cropped to context window). Models have no persistent memory between requests. (Syntax)
- **Stochasticity**: temperature controls randomness (lower = more deterministic). (Syntax)
- **Cost/latency**: attention is quadratic in sequence length, so longer contexts are more expensive; techniques exist but the basic cost is O(T^2). (CS25; implicit)

## From tiny toy to large models (scale intuition)
- **Toy (Karpathy)**: ~10M params, 1M chars of Shakespeare, trains in ~15 min on A100, reaches ~1.48 validation loss on that tiny corpus. (Karpathy GPT)
- **GPT-2 era**: ~1.5B params, ~100B tokens, ~40k USD training cost in 2019. (Karpathy Deep Dive)
- **Modern**: 10-100B+ params, ~10-15T tokens; pretraining takes months on large clusters. (Karpathy Deep Dive)

## Key references in these notes
- Vaswani et al. (2017). "Attention Is All You Need." NeurIPS. https://arxiv.org/abs/1706.03762
- Karpathy's "Let's build GPT from scratch" (kCc8FmEb1nY)
- Karpathy's "Deep Dive into LLMs like ChatGPT" (7xTGNNLPyMI)
- Stanford CS25 "Transformers United" (XfpMkf4rD6E)
- ByteByteGo "Transformers Step-by-Step Explained" (avjX3QrYkls)
- Syntax "LLMs Explained: Tokens, Embeddings, Transformers and More" (YmLp8qe87A0)
- Ondrej "Fine-tune your own LLM in 13 minutes" (g80Q1sVtikE)