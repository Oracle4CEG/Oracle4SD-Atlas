# DOI 登记交接

四位作者已按作者提供的顺序写入 [CITATION.cff](../CITATION.cff)、[作者元数据](../metadata/doi/authors.json)和 [Zenodo 登记 JSON](../metadata/doi/zenodo_metadata.json)：Huaiyu Jia、Siguang Li、Lin William Cong、Luyao Zhang。单位名称和域名照录用户提供的信息；OpenReview 链接只作为个人主页，没有替代或推断 ORCID。

DOI 尚未签发。当前可用的 Hugging Face 凭据可以维护公开数据，但没有可用的 Zenodo 登记凭据或已认证的 DOI 网页会话。对 Hugging Face 设置页的请求返回了站点挑战页，未获得可操作的 DOI 表单；已核查的公开 SDK/API 定义也没有 DOI 登记入口。这个事实不能解释成“作者名单仍缺失”，也不能把元数据文件当作已完成登记。

## 已准备的登记范围

[artifact_plan.json](../metadata/doi/artifact_plan.json)列出三个固定组件：64 份输入、143 份修复结果及验证文件、6 份上游源码归档及清单，共 213 个文件。Atlas 代码归档、采集溯源补充包和登记材料也已[公开归档并逐文件重新下载核验](../metadata/provenance_publication.json)。最终的 [deposit_files.json](../metadata/doi/deposit_files.json)提供 **221 个真实文件、共 19,223,276,635 字节**的完整待登记清单，所有 URL 均锁定不可变版本并附 SHA-256、大小；它本身不是已完成的 DOI 登记。

修复结果包含 95 张正式数据表及 1 张额外实验预测表；其余为清单、字段说明和执行证据。整个 Hugging Face 数据仓库还存有其他研究内容，因此这个 Atlas DOI 的范围应依照上述文件计划，不能把仓库所有内容都署成这篇文章的数据。

## 最后登记步骤

可登录 Zenodo 新建数据集记录，导入上述四位作者及登记字段，按 deposit_files 清单的 `archive_path` 组织并上传真实数据文件、代码和补充材料；仅上传外部 URL 清单不等于归档了数据。`zenodo_metadata.json` 是登记 API 所用的 `metadata` 结构，不是已经存在的远端草稿。实际发行日期若改变，应同步修正 `publication_date`。代码和上游归档须保留各自许可证。[Zenodo 官方登记和上传 API](https://developers.zenodo.org/)说明了认证、上传文件和发布记录的流程。

如果选用 Hugging Face 原生 DOI，需要先确定登记整个仓库当前版本是否符合这份 Atlas 范围，再登录仓库 Settings → DOI → Generate DOI，在自定义作者列表中填入四位作者。其 DOI 对应仓库版本；签发后删除、重命名和更改可见性会受到限制。[Hugging Face 官方 DOI 说明](https://huggingface.co/docs/hub/doi)列出了该流程和版本规则。

发布成功后，保存平台返回的 DOI、记录地址、版本及归档文件哈希，再更新 CITATION、数据卡和版本说明。不要提前填写一个未分配的 DOI。当前工程和数据使用不依赖 DOI；历史采集溯源缺口和真实 Colab 验收仍应分别披露。
