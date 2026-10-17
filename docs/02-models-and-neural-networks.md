# Models, neural networks, and training

## What is an LLM and a "model"?
An LLM is a Large Language Model. The word "model" here means a trained neural network. When you send a prompt to ChatGPT, it goes to a pre-trained model file sitting on a server; that file contains the learned weights of the network. Training happens ahead of time, producing that model file - not at query time.

## What is a neural network?
A neural network is a system of interconnected nodes (neurons) organized into layers. Data flows from the input layer through one or more hidden layers to the output layer. Each connection between neurons has a weight (a number) that controls how much influence one neuron has on the next. The network is essentially a parameterized function: given inputs, weights determine the outputs. (Syntax; Karpathy Deep Dive)

### Key points from the sources
- Weights are the learned numbers - a trained model is literally a file of weight values. (Syntax; Karpathy Deep Dive)
- Layers: neurons are stacked in layers; early layers tend to pick up simple patterns, deeper layers pick up more abstract/compositional ones. (Karpathy GPT; Karpathy Deep Dive)
- Data flows through layers; the network learns by adjusting weights so its outputs match targets. (Syntax)
- Backpropagation (1986 context) is the standard way weights are adjusted during training by propagating error gradients. (Syntax)

## Training a language model
Training a language model means teaching it to predict the next token. At a high level:
1. **Data**: collect and clean text (e.g., internet text filtered/deduped) to form a training corpus. (Karpathy Deep Dive; Syntax)
2. **Tokenization**: convert raw text into tokens (integers) the network can process. (Syntax; Karpathy GPT)
3. **Prediction**: for a sequence of tokens, the network produces logits (unnormalized scores) for the next token.
4. **Loss**: compare predicted next token distribution to the true next token (cross-entropy / negative log likelihood); lower loss means better predictions. (Karpathy GPT)
5. **Optimization**: adjust weights via gradient descent (Adam/AdamW) to reduce loss. (Karpathy GPT)
6. **Scale**: repeat over huge batches for many steps until validation loss stops improving. The result is a pre-trained base model. (Karpathy Deep Dive)

### Dataset scale (for context)
- Tiny Shakespeare (Karpathy's toy example): ~1M characters, ~65-char vocab, trained in minutes on a GPU to produce Shakespeare-like text. (Karpathy GPT)
- Large pretraining: modern runs use trillions of tokens (e.g., FineWeb-scale datasets) and billions of parameters, trained over months on many GPUs. (Karpathy Deep Dive)

## Tokenization and embeddings
- **Tokenization**: split text into subword tokens (often via Byte Pair Encoding, a 1994 compression trick) so rare/compound words don't explode vocabulary. (Syntax; Karpathy Deep Dive)
- **Vocabulary**: a fixed set of tokens; each gets a numeric ID.
- **Embeddings**: map each token ID to a dense vector (a point in high-dimensional space). Vectors capture semantic similarity because tokens that appear in similar contexts end up close together (distributional hypothesis: "you shall know a word by the company it keeps"; word2vec 2013). (Syntax)
- **Vector math**: semantic relationships can appear as vector arithmetic in embedding space (e.g., king − man + woman ≈ queen) - an emergent property. (Syntax)
- **Positional information**: since attention has no inherent sense of order, models add positional embeddings to encode token positions. (ByteByteGo; CS25; Karpathy GPT)

## Autoregressive generation
- The model is trained to predict P(token_{t+1} | token_0,...,token_t).
- At inference time, feed a prompt, sample next token from the distribution (e.g., with temperature/top-p), append it, and repeat - this is autoregressive generation ("one blind token at a time"). (Syntax; Karpathy GPT)
- Context window is the maximum number of tokens the model can see at once; everything beyond is truncated. (Syntax; Karpathy Deep Dive)
- The model has no memory between separate requests - history is provided in the prompt. (Syntax)

## Pretraining vs fine-tuning vs RLHF
- **Pretraining**: train on broad internet text to produce a base model (a document completer). It's general but not inherently a conversational assistant. (Karpathy Deep Dive; Ondrej)
- **Fine-tuning**: continue training on curated datasets (e.g., Q&A pairs in ChatML/ShareGPT format) to teach the model to follow instructions and behave more like an assistant. (Karpathy Deep Dive; Ondrej)
- **LoRA (Low-Rank Adaptation)**: a common, efficient fine-tuning method where only small adapter parameters are trained instead of all weights. (Ondrej)
- **Alignment (RLHF/RL on verifiable tasks)**: use human feedback or verifiable rewards to shape outputs (e.g., prefer helpful/harmless answers). Modern "thinking" models also use RL on verifiable problems so reasoning traces can emerge. (Karpathy Deep Dive)
- **Inference**: running the trained model to generate answers (as opposed to training). (Ondrej)

## Takeaway
A "model" = a neural network (weights + architecture). Training = next-token prediction over data. The result is a probabilistic sequence predictor; post-training (fine-tuning/RLHF) adapts that predictor into a more useful assistant. This is the core conceptual split from the rule-based systems described in doc 01.