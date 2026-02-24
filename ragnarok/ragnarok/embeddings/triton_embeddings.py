# -*- coding: utf-8 -*-
"""
    ragnarok.embeddings.triton_embeddings
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Embedding algorithms hosted on Triton.
"""

import socket
from contextlib import suppress

import gevent.ssl
import numpy as np
import tritonclient.http as httpclient

from common.config import CONFIG
from common.core import get_component_logger
from common.models.enums import ModelProvider
from common.utils.misc import generate_batches
from ragnarok.embeddings.base import EmbeddingBase

logger = get_component_logger()

MODEL_DIMS = {
    "distiluse-base-multilingual-cased-v2-pipeline": 512,
    "use-large4": 512,
}


class TritonEmbeddings(EmbeddingBase):

    def __init__(self, model_name: str = "distiluse-base-multilingual-cased-v2-pipeline"):
        self.client = self._get_triton_client()

        super().__init__(
            provider=ModelProvider.Triton,
            model_name=model_name,
            dim=MODEL_DIMS.get(model_name, 0),
        )

    def vector(self, s: str, normalize: bool = True) -> np.ndarray:
        return self.vector_batch([s], normalize=normalize)[0]

    def vector_batch(self, batch: list[str], normalize: bool = True, timeout: float | None = None) -> np.ndarray:
        result = None

        for batch_slice in generate_batches(batch, 128):
            sentence = np.array(batch_slice, dtype=object).reshape(-1)
            inputs = [httpclient.InferInput("inputs", [len(sentence)], "BYTES")]
            inputs[0].set_data_from_numpy(sentence, binary_data=True)
            inputs[0].set_shape([len(sentence), 1])
            outputs = [httpclient.InferRequestedOutput("outputs", binary_data=True)]

            res = self._infer(inputs, outputs, timeout=timeout)
            result = res if result is None else np.append(result, res, axis=0)

        # embeddings are already normalized
        result = np.array([]) if result is None else result
        return result.reshape(-1, self.dim)

    def _infer(self, inputs, outputs, timeout: float | None = None):

        if timeout is not None:
            client = self._get_triton_client(network_timeout=timeout)
            return client.infer(model_name=self.model_name, inputs=inputs, outputs=outputs).as_numpy("outputs")

        with suppress(socket.timeout):
            return self.client.infer(model_name=self.model_name, inputs=inputs, outputs=outputs).as_numpy("outputs")

        logger.warning("Failed to get response from Triton inference server within the base timeout duration")

        for nt in (5.0, 10.0):
            with suppress(socket.timeout):
                client = self._get_triton_client(network_timeout=nt)
                return client.infer(model_name=self.model_name, inputs=inputs, outputs=outputs).as_numpy("outputs")

        raise socket.timeout("Call to Triton inference server timed out")

    @staticmethod
    def _get_triton_client(network_timeout: float = 2.0) -> httpclient.InferenceServerClient | None:

        if CONFIG.TRITON_URL is None:
            return None

        # noinspection PyUnresolvedReferences
        return httpclient.InferenceServerClient(
            url=CONFIG.TRITON_URL.host,
            ssl=CONFIG.TRITON_URL.scheme == "https",
            ssl_context_factory=gevent.ssl.create_default_context,
            network_timeout=network_timeout,
            verbose=False,
        )
