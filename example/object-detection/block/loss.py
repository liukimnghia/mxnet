"""Custom losses for object detection.
Losses are used to penalize incorrect classification and inaccurate box regression.
Losses are subclasses of gluon.loss.Loss which is a HybridBlock actually.
"""
from mxnet.gluon import loss
from mxnet.gluon.loss import _reshape_like, _apply_weighting
import numpy as np

def find_inf(x, mark='null'):
    pos = np.where(x.asnumpy().flat == np.inf)[0]
    print(mark, pos)


class SmoothL1Loss(loss.Loss):
    """SmoothL1 loss for finer grade regression.
    SmoothL1 is introduced in

    """
    def __init__(self, sigma=1., weight=None, batch_axis=0, **kwargs):
        super(SmoothL1Loss, self).__init__(weight, batch_axis, **kwargs)
        self._sigma = sigma

    def hybrid_forward(self, F, pred, label, sample_weight=None):
        label = _reshape_like(F, label, pred)
        loss = F.smooth_l1(pred - label, scalar=self._sigma)
        loss = _apply_weighting(F, loss, self._weight, sample_weight)
        return F.mean(loss, axis=self._batch_axis, exclude=True)

class SigmoidBinaryCrossEntropyLoss(Loss):
    r"""The cross-entropy loss for binary classification. (alias: SigmoidBCELoss)

    BCE loss is useful when training logistic regression. If `from_sigmoid`
    is False (default), this loss computes:

    .. math::

        prob = \frac{1}{1 + \exp(-{pred})}

        L = - \sum_i {label}_i * \log({prob}_i) +
            (1 - {label}_i) * \log(1 - {prob}_i)

    If `from_sigmoid` is True, this loss computes:

    .. math::

        L = - \sum_i {label}_i * \log({pred}_i) +
            (1 - {label}_i) * \log(1 - {pred}_i)


    `pred` and `label` can have arbitrary shape as long as they have the same
    number of elements.

    Parameters
    ----------
    from_sigmoid : bool, default is `False`
        Whether the input is from the output of sigmoid. Set this to false will make
        the loss calculate sigmoid and BCE together, which is more numerically
        stable through log-sum-exp trick.
    weight : float or None
        Global scalar weight for loss.
    batch_axis : int, default 0
        The axis that represents mini-batch.


    Inputs:
        - **pred**: prediction tensor with arbitrary shape
        - **label**: target tensor with values in range `[0, 1]`. Must have the
          same size as `pred`.
        - **sample_weight**: element-wise weighting tensor. Must be broadcastable
          to the same shape as pred. For example, if pred has shape (64, 10)
          and you want to weigh each sample in the batch separately,
          sample_weight should have shape (64, 1).

    Outputs:
        - **loss**: loss tensor with shape (batch_size,). Dimenions other than
          batch_axis are averaged out.
    """
    def __init__(self, from_sigmoid=False, weight=None, batch_axis=0, **kwargs):
        super(SigmoidBinaryCrossEntropyLoss, self).__init__(weight, batch_axis, **kwargs)
        self._from_sigmoid = from_sigmoid

    def hybrid_forward(self, F, pred, label, sample_weight=None):
        label = _reshape_like(F, label, pred)
        if not self._from_sigmoid:
            max_val = F.relu(-pred)
            loss = pred - pred*label + max_val + F.log(F.exp(-max_val)+F.exp(-pred-max_val))
        else:
            loss = -(F.log(pred+1e-12)*label + F.log(1.-pred+1e-12)*(1.-label))
        loss = _apply_weighting(F, loss, self._weight, sample_weight)
        return F.mean(loss, axis=self._batch_axis, exclude=True)

SigmoidBCELoss = SigmoidBinaryCrossEntropyLoss


class SoftmaxCrossEntropyLoss(Loss):
    r"""Computes the softmax cross entropy loss. (alias: SoftmaxCELoss)

    If `sparse_label` is `True` (default), label should contain integer
    category indicators:

    .. math::

        \DeclareMathOperator{softmax}{softmax}

        p = \softmax({pred})

        L = -\sum_i \log p_{i,{label}_i}

    `label`'s shape should be `pred`'s shape with the `axis` dimension removed.
    i.e. for `pred` with shape (1,2,3,4) and `axis = 2`, `label`'s shape should
    be (1,2,4).

    If `sparse_label` is `False`, `label` should contain probability distribution
    and `label`'s shape should be the same with `pred`:

    .. math::

        p = \softmax({pred})

        L = -\sum_i \sum_j {label}_j \log p_{ij}

    Parameters
    ----------
    axis : int, default -1
        The axis to sum over when computing softmax and entropy.
    sparse_label : bool, default True
        Whether label is an integer array instead of probability distribution.
    from_logits : bool, default False
        Whether input is a log probability (usually from log_softmax) instead
        of unnormalized numbers.
    weight : float or None
        Global scalar weight for loss.
    batch_axis : int, default 0
        The axis that represents mini-batch.
    ignore_label : int, default -1
        The label to be ignored for calculating loss.


    Inputs:
        - **pred**: the prediction tensor, where the `batch_axis` dimension
          ranges over batch size and `axis` dimension ranges over the number
          of classes.
        - **label**: the truth tensor. When `sparse_label` is True, `label`'s
          shape should be `pred`'s shape with the `axis` dimension removed.
          i.e. for `pred` with shape (1,2,3,4) and `axis = 2`, `label`'s shape
          should be (1,2,4) and values should be integers between 0 and 2. If
          `sparse_label` is False, `label`'s shape must be the same as `pred`
          and values should be floats in the range `[0, 1]`.
        - **sample_weight**: element-wise weighting tensor. Must be broadcastable
          to the same shape as label. For example, if label has shape (64, 10)
          and you want to weigh each sample in the batch separately,
          sample_weight should have shape (64, 1).

    Outputs:
        - **loss**: loss tensor with shape (batch_size,). Dimenions other than
          batch_axis are averaged out.
    """
    def __init__(self, axis=-1, sparse_label=True, from_logits=False, weight=None,
                 batch_axis=0, ignore_label=-1, **kwargs):
        super(SoftmaxCrossEntropyLoss, self).__init__(weight, batch_axis, **kwargs)
        self._axis = axis
        self._sparse_label = sparse_label
        self._from_logits = from_logits
        self._ignore_label = ignore_label

    def hybrid_forward(self, F, pred, label, sample_weight=None):
        if not self._from_logits:
            pred = F.log_softmax(pred, self._axis)
        if self._sparse_label:
            loss = -F.pick(pred, label, axis=self._axis, keepdims=True)
            loss = F.where(label.reshape_like(loss) == self._ignore_label,
                           F.zeros_like(loss), loss)
        else:
            label = _reshape_like(F, label, pred)
            loss = -F.sum(pred*label, axis=self._axis, keepdims=True)
        loss = _apply_weighting(F, loss, self._weight, sample_weight)
        return F.mean(loss, axis=self._batch_axis, exclude=True)


class FocalLoss(loss.Loss):
    """Focal Loss for inbalanced classification.
    Focal loss was described in https://arxiv.org/abs/1708.02002

    Parameters
    ----------
    pending
    """
    def __init__(self, axis=-1, alpha=0.25, gamma=2, sparse_label=True,
                 from_logits=False, batch_axis=0, weight=None, num_class=None,
                 eps=1e-12, **kwargs):
        super(FocalLoss, self).__init__(weight, batch_axis, **kwargs)
        self._axis = axis
        self._alpha = alpha
        self._gamma = gamma
        self._sparse_label = sparse_label
        if sparse_label and (not isinstance(num_class, int) or (num_class < 1)):
            raise ValueError("Number of class > 0 must be provided if sparse label is used.")
        self._num_class = num_class
        self._from_logits = from_logits
        self._eps = eps

    def hybrid_forward(self, F, output, label, sample_weight=None):
        # find_inf(output, 'output')
        # backup = output.asnumpy()
        if not self._from_logits:
            output = F.sigmoid(output)
        if self._sparse_label:
            one_hot = F.one_hot(label, self._num_class)
        else:
            one_hot = label > 0
        pt = F.where(one_hot, output, 1 - output)
        # print('pt', pt)
        # find_inf(pt, 'pt')
        t = F.ones_like(one_hot)
        alpha = F.where(one_hot, self._alpha * t, (1 - self._alpha) * t)
        # find_inf(alpha, 'alpha')
        # tmp1 = (1-pt) ** self._gamma
        # print('tmp1',tmp1)
        # find_inf(tmp1, 'tmp1')
        # tmp2 = F.log(pt)
        # find_inf(tmp2, 'tmp2')
        # tmp3 = -alpha * tmp1
        # find_inf(tmp3, 'tmp3')
        # tmp4 = tmp1 * tmp2
        # find_inf(tmp4, 'tmp4')
        loss = -alpha * ((1 - pt) ** self._gamma) * F.log(F.minimum(pt + self._eps, 1))
        # print('pt again', pt)
        # find_inf(loss, 'loss')
        # import numpy as np
        # np.set_printoptions(threshold=np.inf)
        # temp = loss.asnumpy()
        # pos = np.where(temp.flat == np.inf)[0]
        # print(temp.dtype)
        # print(alpha.asnumpy().flat[pos], 'alpha pos')
        # print(tmp2.asnumpy().flat[pos], 'log results pos')
        # print(tmp1.asnumpy().flat[pos], 'power')
        # print(pt.asnumpy().flat[pos], 'in pt')
        # print(output.asnumpy().flat[pos], 'in output')
        # print(backup.flat[pos], 'in backup')
        # print(pos)
        # print(temp.flat[pos])
        # print(np.sum(temp))
        # print(F.sum(loss,axis=self._batch_axis, exclude=True))
        # raise
        loss = _apply_weighting(F, loss, self._weight, sample_weight)
        return F.mean(loss, axis=self._batch_axis, exclude=True)
