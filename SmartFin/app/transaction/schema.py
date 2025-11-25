import strawberry
from .mutations import TransactionMutations
from .queries import TransactionQueries

TransactionQuery = TransactionQueries
TransactionMutation = TransactionMutations