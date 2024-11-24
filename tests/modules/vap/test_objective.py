import numpy as np
import torch

from src.modules.vap.vap import ObjectiveVAP as NumpyVAP
from src.modules.vap.objective import ObjectiveVAP as PyTorchVAP

# PyTorch版とNumPy版の両方のコードをインポート
# PyTorch版をPyTorchVAP、NumPy版をNumpyVAPとしてインポートすると仮定

def debug_codebook():
    # PyTorch版とNumPy版のコードベクトルを直接比較
    torch_vap = PyTorchVAP()
    numpy_vap = NumpyVAP()
    
    torch_codes = torch_vap.codebook.emb.weight.data.numpy()
    numpy_codes = numpy_vap.codebook.codes
    
    print("Code vectors comparison:")
    print("Max difference:", np.abs(torch_codes - numpy_codes).max())
    print("\nFirst few vectors (PyTorch):")
    print(torch_codes[:5])
    print("\nFirst few vectors (NumPy):")
    print(numpy_codes[:5])


def test_implementations():
    # テストデータの生成
    batch_size = 2
    time_steps = 100
    n_speakers = 2
    
    # 同じ乱数シードを設定
    np.random.seed(42)
    torch.manual_seed(42)
    
    # モデルのインスタンス化
    vap_torch = PyTorchVAP()
    vap_numpy = NumpyVAP()
    
    # horizonを考慮してテストデータを生成
    required_frames = vap_torch.horizon + 1
    time_steps = max(time_steps, required_frames + 10)  # 余裕を持たせる
    
    # 入力データの生成
    va_np = np.random.rand(batch_size, time_steps, n_speakers).astype(np.float32)
    va_torch = torch.from_numpy(va_np).float()

    # 許容誤差を定義
    ATOL = 1e-6
    RTOL = 1e-5

    # 1. ProjectionWindowの比較
    proj_torch = vap_torch.projection_window_extractor(va_torch).numpy()
    proj_numpy = vap_numpy.projection_window_extractor(va_np)
    
    print("ProjectionWindow comparison:")
    max_diff = np.abs(proj_torch - proj_numpy).max()
    print(f"Max difference: {max_diff}")
    print(f"Within tolerance: {max_diff <= ATOL}")
    print("Shapes match:", proj_torch.shape == proj_numpy.shape)
    if max_diff > ATOL:
        print("Warning: ProjectionWindow differences exceed tolerance!")
        print("Sample differences:")
        diff = np.abs(proj_torch - proj_numpy)
        indices = np.where(diff > ATOL)
        for i in range(min(5, len(indices[0]))):
            idx = tuple(ind[i] for ind in indices)
            print(f"Index {idx}: torch={proj_torch[idx]}, numpy={proj_numpy[idx]}")

    # 2. Codebookのエンコード結果の比較
    # import pdb; pdb.set_trace()
    labels_torch = vap_torch.get_labels(va_torch).numpy()
    labels_numpy = vap_numpy.get_labels(va_np)
    
    print("\nCodebook encode comparison:")
    max_diff = np.abs(labels_torch - labels_numpy).max()
    print(f"Max difference: {max_diff}")
    print(f"Within tolerance: {max_diff <= ATOL}")
    print("Shapes match:", labels_torch.shape == labels_numpy.shape)
    if max_diff > ATOL:
        print("Warning: Codebook differences exceed tolerance!")
        print("Sample differences:")
        diff = np.abs(labels_torch - labels_numpy)
        indices = np.where(diff > ATOL)
        for i in range(min(5, len(indices[0]))):
            idx = tuple(ind[i] for ind in indices)
            print(f"Index {idx}: torch={labels_torch[idx]}, numpy={labels_numpy[idx]}")

    # 3. get_probsの比較
    n_classes = 2 ** (vap_torch.projection_window_extractor.total_bins)
    valid_frames = time_steps - vap_torch.horizon
    logits_np = np.random.randn(batch_size, valid_frames, n_classes).astype(np.float32)
    logits_torch = torch.from_numpy(logits_np).float()

    probs_torch = vap_torch.get_probs(logits_torch)
    probs_numpy = vap_numpy.get_probs(logits_np)

    print("\nget_probs comparison:")
    for key in probs_torch:
        torch_val = probs_torch[key].numpy()
        numpy_val = probs_numpy[key]
        max_diff = np.abs(torch_val - numpy_val).max()
        print(f"\n{key}:")
        print(f"Max difference: {max_diff}")
        print(f"Within tolerance: {max_diff <= ATOL}")
        print("Shapes match:", torch_val.shape == numpy_val.shape)
        if max_diff > ATOL:
            print(f"Warning: {key} differences exceed tolerance!")
            print("Sample differences:")
            diff = np.abs(torch_val - numpy_val)
            indices = np.where(diff > ATOL)
            for i in range(min(5, len(indices[0]))):
                idx = tuple(ind[i] for ind in indices)
                print(f"Index {idx}: torch={torch_val[idx]}, numpy={numpy_val[idx]}")

    # 4. Dialog statesの比較
    ds_torch = vap_torch.window_to_win_dialog_states(
        vap_torch.projection_window_extractor(va_torch)
    ).numpy()
    ds_numpy = vap_numpy.window_to_win_dialog_states(
        vap_numpy.projection_window_extractor(va_np)
    )

    print("\nDialog states comparison:")
    max_diff = np.abs(ds_torch - ds_numpy).max()
    print(f"Max difference: {max_diff}")
    print(f"Within tolerance: {max_diff <= ATOL}")
    print("Shapes match:", ds_torch.shape == ds_numpy.shape)
    if max_diff > ATOL:
        print("Warning: Dialog states differences exceed tolerance!")
        print("Sample differences:")
        diff = np.abs(ds_torch - ds_numpy)
        indices = np.where(diff > ATOL)
        for i in range(min(5, len(indices[0]))):
            idx = tuple(ind[i] for ind in indices)
            print(f"Index {idx}: torch={ds_torch[idx]}, numpy={ds_numpy[idx]}")

if __name__ == "__main__":
    debug_codebook()
    test_implementations()