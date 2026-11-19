# 参考文献与方法来源

本文件列出 `reference-relevant` 的方法依据。列表服务于实现追溯与进一步阅读，不代表本项目复现了所有列出系统的实验设置或结果。

## 引用功能与需求识别

- Teufel, S., Siddharthan, A., & Tidhar, D. (2006). An annotation scheme for citation function. *Proceedings of the 7th SIGdial Workshop on Discourse and Dialogue*. https://aclanthology.org/W06-1610/
- Jurgens, D., et al. (2018). The ACL Anthology Reference Corpus: A reference dataset for bibliographic research in computer science. *LREC 2018*. https://aclanthology.org/L18-1554/
- Cohan, A., Ammar, W., van Zuylen, M., & Cady, F. (2019). Structural scaffolds for citation intent classification in scientific publications. *NAACL 2019*. https://aclanthology.org/N19-1361/
- Zhang, Y., Wang, Y., Sheng, Q. Z., Yao, L., Chen, H., Wang, K., Mahmood, A., Zhang, E. W., et al. (2025). Deep learning meets bibliometrics: A survey of citation function classification. *Journal of Informetrics, 19*(1), 101608. https://doi.org/10.1016/j.joi.2024.101608
- Paolini, L., et al. (2025). CiteFusion: An ensemble framework for citation intent classification harnessing dual-model binary couples and SHAP analyses. *Scientometrics, 130*, 5911–5981. https://doi.org/10.1007/s11192-025-05418-8
- Yang, J., & Du, Z. (2026). Box-enhanced context fusion for citation intent classification. *Neural Networks*. https://doi.org/10.1016/j.neunet.2026.108962

## 引用必要性与正文—引用对齐

- He, Q., Pei, J., Kifer, D., Mitra, P., & Giles, C. L. (2010). Context-aware citation recommendation. *WWW 2010*. https://doi.org/10.1145/1772690.1772756
- Bhagavatula, C., Feldman, S., Power, R., Ammar, W., & van Zuylen, M. (2018). Content-based citation recommendation. *NAACL 2018*. https://arxiv.org/abs/1802.08301
- Zeng, T., & Acuna, D. E. (2020). Modeling citation worthiness by using attention-based bidirectional LSTM networks and interpretable models. *Scientometrics*. https://arxiv.org/abs/2405.12206
- Wright, D., & Augenstein, I. (2021). CiteWorth: Cite-worthiness detection for improved scientific document understanding. *Findings of ACL 2021*. https://aclanthology.org/2021.findings-acl.157.pdf
- Wadden, D., et al. (2020). Fact or fiction: Verifying scientific claims. *EMNLP 2020*. https://arxiv.org/abs/2004.14974

## 支撑性、归因与引用质量评估

- Rashkin, H., et al. (2023). Measuring attribution in natural language generation models. *Computational Linguistics*. https://aclanthology.org/2023.cl-4.17/
- Gao, T., et al. (2023). ALCE: Automatic LLM citation evaluation. *EMNLP 2023*. https://aclanthology.org/2023.emnlp-main.91/
- Asai, A., et al. (2024). OpenScholar: Synthesizing scientific literature with retrieval-augmented LMs. https://arxiv.org/abs/2411.14199
- CiteEval / CiteBench (2025). Principle-driven citation evaluation for source attribution. https://arxiv.org/abs/2506.01829
- Hong, M., et al. (2026). CiteLLM: An agentic platform for trustworthy scientific reference discovery. *WWW Companion 2026*. https://arxiv.org/abs/2602.23075
- ReCite (2026). Agentic reasoning for faithful citation. https://arxiv.org/abs/2609.09156

## 文档表示、候选检索与重排

- Cohan, A., et al. (2020). SPECTER: Document-level representation learning using citation-informed transformers. *ACL 2020*. https://aclanthology.org/2020.acl-main.540/
- Ostendorff, M., et al. (2022). Neighborhood contrastive learning for scientific document representations with citation embeddings. *EMNLP 2022*. https://aclanthology.org/2022.emnlp-main.802/
- Singh, A., et al. (2022). SciRepEval: A multi-format benchmark for scientific document representations. *EMNLP 2022*. https://arxiv.org/abs/2211.13308
- Färber, M., & Jatowt, A. (2020). Citation recommendation: Approaches and datasets. *Scientometrics*. https://doi.org/10.1007/s11192-020-03422-8

## 置信度与自动化判断的可靠性

- Guo, C., et al. (2017). On calibration of modern neural networks. *ICML 2017*. https://arxiv.org/abs/1706.04599
- Tian, Z., et al. (2025). Overconfidence in LLM-as-a-Judge: Diagnosis and confidence-driven solution. https://arxiv.org/abs/2508.06225

## 与本项目设计的关系

- 引用功能分类为「需求识别」提供标签基础；本项目保留经管特有的理论依据、数据/测量来源与识别策略等类别。
- 引用必要性与 cite-worthiness 研究说明上下文和学科惯例的重要性；本项目只对高风险未引用区域做保守提醒。
- SciFact、AIS、ALCE 与 CiteEval 支撑「主张—证据」核验思路；本项目区分支持、反驳与中性提及，并在证据不足时弃权。
- SPECTER / SPECTER2 / SciNCL 支撑候选语义召回；本项目以可选项接入，依赖缺失时明确回退到词法召回。
- 校准研究支撑置信度上限与弃权机制；本项目尚未声称完成统计意义上的充分校准。
