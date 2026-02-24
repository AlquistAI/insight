# -*- coding: utf-8 -*-
"""
    common.models.defaults
    ~~~~~~~~~~~~~~~~~~~~~~

    Default values used throughout the project.
"""

from common.models import enums

#############
## GENERAL ##
#############

# Project/content language
LANG = "cs-CZ"

###############
## RETRIEVAL ##
###############

# Embedding model
MODEL_EMB = "text-embedding-3-large"
PROVIDER_EMB = enums.ModelProvider.OpenAI

# K-closest matches found by BM25 search
K_BM25 = 5

# K-closest matches found by cosine similarity
K_EMB = 5

# Number of candidates for KNN-search in vector DB
NUM_CANDIDATES = 100

###############
## RERANKING ##
###############

# Reranking model
MODEL_RERANK = "rerank-v3.5"
PROVIDER_RERANK = enums.ModelProvider.Cohere

# K-closest matches after reranking
K_RERANK = 5

################
## GENERATION ##
################

# LLM
MODEL_LLM = "gpt-4o"
PROVIDER_LLM = enums.ModelProvider.OpenAI
TEMPERATURE = 0.7
