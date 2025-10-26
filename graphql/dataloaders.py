# config/graphql/dataloaders.py
from strawberry.dataloader import DataLoader
from apps.account.selectors import get_profiles_by_ids

def build_dataloaders():
    return {
        "profileById": DataLoader(load_fn=get_profiles_by_ids),
        # здесь же позже добавим assetById, userById, fxRateByPairAndTs и т.п.
    }
