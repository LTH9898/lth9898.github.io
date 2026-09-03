---
title: "Flow Matching: velocity fields instead of score functions"
description: A short worked example showing every feature this blog supports.
tags: [generative, flow-matching]
---

This draft exists to show the syntax. Move it into `_posts/` (with a
`YYYY-MM-DD-` filename prefix) to publish it, or delete it once you have
written your own first post.

## Math

Inline math uses single dollars: the velocity field $v_\theta(x_t, t)$ is
trained to match $u_t = x_1 - x_0$.

Display math uses double dollars:

$$
\mathcal{L}_{\text{FM}}(\theta)
= \mathbb{E}_{t \sim \mathcal{U}[0,1],\, x_0 \sim p_0,\, x_1 \sim p_1}
  \left[ \left\| v_\theta(x_t, t) - (x_1 - x_0) \right\|^2 \right],
\qquad x_t = (1-t)\,x_0 + t\,x_1.
$$

## Code

Fenced blocks get syntax highlighting. Name the language after the fence:

```python
def flow_matching_loss(model, x0, x1):
    t = torch.rand(x0.shape[0], device=x0.device)
    xt = (1 - t).view(-1, 1, 1, 1) * x0 + t.view(-1, 1, 1, 1) * x1
    target = x1 - x0
    return (model(xt, t) - target).pow(2).mean()
```

Inline `code` works too.

## Images

Put files under `images/blog/<slug>/` and reference them from the site root:

```markdown
![Trajectories under rectified flow](/images/blog/example-post/trajectories.png)
```

## Tables, quotes, lists

| Method | NFE | FID |
| --- | --- | --- |
| Diffusion | 250 | 2.27 |
| Rectified Flow | 1 | 4.85 |

> Blockquotes render with a left rule.

1. Ordered lists work.
2. So do unordered ones:
   - nested
   - items
