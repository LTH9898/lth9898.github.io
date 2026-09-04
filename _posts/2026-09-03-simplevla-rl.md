---
title: "SimpleVLA-RL"
description: "RL in VLA"
tags: [VLA, RL, Paper]
notion_page_id: 3d0c534b-e6e2-800d-8539-f324aa14b35e
notion_last_edited: 2026-09-04T06:43:00.000Z
---

## Motivation

1. RL improved step-by-step reasoning capabilities in Large Language Models
2. So can RL **similiary improve the long-horizon step-by-step planning of VLA?**

## Contribution

![](/images/blog/simplevla-rl/01-image.png)

1. Achieved SoTA performance on LIBERO
2. Training well without large-scale dataset.
3. Emerging property, “pushCut”

## Quick RL recap

### LLM - formulation

- **State**

$$
s_t = (x_\text{prompt},y_1,y_2, \dots y_{t-1})
$$

- **Action ( Next token prediction)**

$$
a_t = y_t\in \mathcal{V} \quad \text{where} \quad y_t\sim\pi_\theta(\cdot|s_t) = \text{softmax}(f_\theta(s_t)/T)
$$

- **Environment ( provide rewards)**
  - ver. Descrete

    $$
    r(\tau) = \begin{cases} 1, & \text{if } \tau \text{ satisfies correctness criteria} \\ 0, & \text{otherwise} \end{cases}
    $$
  - ver. Continuous

    $$
    \quad r(\tau) = R_\phi(\tau) \in [0, 1]
    $$
- **Rollout**
  - LLM auto-regressively generates a sequence by sampling tokens from $\pi_\theta(y_t|s_t)$ until eos token. ( without intermediate feedback )

### VLA-formulation

- **State**

$$
s_t=(o_t^{vis}, o_t^{prop},l_{task})
$$

$o_t^{vis}$ : multi-view(modal?) observation

$o_t^{prop}$ : proprioceptive information ( initial pose ! )

$l_{task}$ : textual instruction ( 설거지해라, 빨간공 집어라 등등 )

- **Action**

$$
a_t = Decoder(h_\theta(s_t)), \\\quad Decoder \in \{\text{Diffusion Expert}, \text{Action Tokenizer}\}, a_t\in R^d
$$

State (observation) encodes to the hidden state $h_\theta(s_t)$

- **Environment**

$$
r_t = \alpha \cdot I_{\text{success}} + (1 - \alpha) \cdot \sum_{i} w_i \cdot \phi_i(s_t, a_t), \quad \alpha \in [0,1],\\ \quad I_{\text{success}} = \begin{cases} 1, & \text{if task success} \\ 0, & \text{otherwise} \end{cases}
$$

Linear combination of intermediate ( process reward ) and task reward

Process reward : (Distance to goal, …)

- **Rollout**

Policy $\pi_\theta$

Input : $s_t$ / Output : $(a_t, a_{t+1}, \dots,a_{t+k-1})$

Continues until task completion or reaching maximum episode length.

$$
trajectory \space \tau = ((s_0,a_0),(s_1,a_1),\dots,(s_T,a_T))
$$

### GRPO

RL method that eliminates the value function by computing through group-relative normalization.

$$
J_{\text{GRPO}}(\theta) = \mathbb{E}_{s_0 \sim \mathcal{D}, \{\tau_i\} \sim \pi_{\theta_{\text{old}}}} \left[ \frac{1}{G} \sum_{i=1}^{G} \frac{1}{|\tau_i|} \sum_{t=1}^{|\tau_i|} \min\left(r_{i,t}(\theta)\hat{A}_i, \text{clip}(r_{i,t}(\theta), 1-\varepsilon, 1+\varepsilon)\hat{A}_i\right) - \beta D_{\text{KL}}(\pi_\theta \| \pi_{\text{ref}}) \right]
$$

Importance sampling ratio $r_{i,t}(\theta)$ , Normalized advantage $\hat A_i$

$$
r_{i,t}(\theta) = \frac{\pi_\theta(a_{i,t}|s_{i,t})}{\pi_{\theta_{\text{old}}}(a_{i,t}|s_{i,t})}, \quad \hat{A}_i = \frac{R_i - \text{mean}(\{R_i\}_{i=1}^{G})}{\text{std}(\{R_i\}_{i=1}^{G})}
$$

![](/images/blog/simplevla-rl/02-image.png)

### LLM vs VLA

- LLM rollout : Proceeds by autoregressively generating tokens until reaching a stop token or max output length
- VLA rollout : continuous interaction with the env to update the visual observation and robot state dynamically

![](/images/blog/simplevla-rl/03-image.png)

## Simple VLA-RL

### Reward

Every RL systems should define Reward.. Let’s see how the SimpleVLA-RL defined it! 😃

$$
R(a_{i,t} \mid s_{i,t}) = \begin{cases} 1, & \text{is\_successful}[\text{traj.}(a_i, s_i)] \\ 0, & \text{otherwise} \end{cases}
$$

Trajectory-level rewards are uniformly propagated to the individual action tokens.

### Exploration strategy

#### Dynamic Sampling

GRPO’s problem ! → when all trajectories share identical rewards, their advantage estimation becomes zero, resulting in null gradients and causing unstable training dynamics.

$$
0 < |\{\text{traj.}(a_i, s_i) \mid \text{is\_successful}[\text{traj.}(a_i, s_i)]\}| < G
$$

성공한 Trajectories 의 개수가 0개보다 크고, G개(총 개수)보다 작아야 한다. 일부는 성공하고 일부는 실패한 결과를 사용하여, Advantage 가 0이되어 학습이 안되는 경우를 막음.

#### Clipping Higher

PPO and GRPO employ clipping over the importance sampling ratio to restrict the trust region and enhance RL stability.

Exploration의 영향을 더 많이 주기 위해서, modify clipping range in the GRPO training objective from \[0.8, 1.2\] to \[0.8, 1.28\]

#### Higher Rollout Temperature

Recent works on LLM RL adjusting the rollout temperature to promote exploration.

Recap the action sampling..

$$
a_t = y_t\in \mathcal{V} \quad \text{where} \quad y_t\sim\pi_\theta(\cdot|s_t) = \text{softmax}(f_\theta(s_t)/T)
$$

If $T$ grows bigger, the distribution become flatter..! so, it gives more chance to the unlikely actions. → More exploration.

![](/images/blog/simplevla-rl/04-image.png)

#### Objective ( Loss )

$$
\mathcal{J}(\theta) = \mathbb{E}_{s_0 \sim \mathcal{D},\, \{a_t\}_{i=1}^{G} \sim \pi_{\theta_{old}}(\cdot|s_t)} \left[ \frac{1}{G} \sum_{i=1}^{G} \frac{1}{|a_i|} \sum_{t=1}^{|a_i|} \min\left( r_{i,t}(\theta)\hat{A}_i,\ \text{clip}\left(r_{i,t}(\theta), 1-\varepsilon_{low}, 1+\varepsilon_{high}\right)\hat{A}_i \right) \right] \\
\text{s.t.} \quad 0 < \left| \{ \text{traj}_i(a_i, s_i) \mid \text{is\_successful}[\text{traj}_i(a_i, s_i)] \} \right| < G, \\
r_{i,t}(\theta) = \frac{\pi_\theta(a_{i,t} \mid s_{i,t})}{\pi_{\theta_{old}}(a_{i,t} \mid s_{i,t})}, \qquad \hat{A}_i = \frac{R_i - \text{mean}(\{R_i\}_{i=1}^{G})}{\text{std}(\{R_i\}_{i=1}^{G})}
$$

## Experiments

- Backbones : OpenVLA-OFT
- Use only **single view images,** language instructions, and robot proprioceptive states as model inputs.
  - Official OpenVLA used wrist images
  - LIBERO dataset - didn’t used proprioceptive states in model inputs.
- Output head
  - LLaMA2 head for action token generation
  - Official model uses an MLP to generate continuous actions.

## Results

- LIBERO, RoboTwin-1.0, RoboTwin-2.0

- OpenVLA-OFT : SimpleVLA-RL

  ![](/images/blog/simplevla-rl/05-image.png)

![](/images/blog/simplevla-rl/06-image.png)

![](/images/blog/simplevla-rl/07-image.png)

![](/images/blog/simplevla-rl/08-image.png)

## Analysis

#### Data Scarcity

|   | Spatial | Object | Goal | Long | Avg |
| --- | --- | --- | --- | --- | --- |
| One-Traj SFT | 63.6 | 54.9 | 59.6 | 17.3 | 48.9 |
| One-Traj + RL | 98.2 | 98.7 | 98.8 | 91.7 | **96.9** |

- One-trajectory SFT : use only one demo data
- Full-trajectory SFT : use 500 demo data

#### Generalization

Compare SFT and RL on unseen tasks

- LIBERO-Spatial/Obejct/Goal ( each have 10 tasks. - 9 tasks (seen), 1 task (unseen)
- Two stage learning
  - One-Trajectory SFT
  - SFT - Additional fine\_tuning on 9 seen tasks  vs simpleVLA-RL

    ![](/images/blog/simplevla-rl/09-image.png)
  - SFT shows overfitting
  - RL learns general skills by RL

#### Real world

|   | Stack Bowls | Place Empty Cup | Pick Bottle | Click Bell | Avg |
| --- | --- | --- | --- | --- | --- |
| RDT | 60.0 | 4.0 | 10.0 | 20.0 | 23.5 |
| OpenVLA-OFT (SFT) | 38.0 | 2.0 | 0.0 | 30.0 | 17.5 |
| w/ ours (RL) | 70.0 | 10.0 | 14.0 | 60.0 | **38.5** |

## Discussion

#### Emergent property - PushCut

![](/images/blog/simplevla-rl/10-image.png)

- VLA with RL autonomously discovers a more efficient solution
  - Instead of grasping , pushing.

## TODO

- [ ] *RL 배웠었는데, 많이 까먹음.. MDP 부터 최신(?) GRPO까지 빠른 시일 내에 한번 리뷰하기로..*
