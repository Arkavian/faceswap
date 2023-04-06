import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers as klayers
from .transformer import Transformer
from tensorflow.keras.models import Model
from tensorflow.keras import backend as K
from tensorflow.keras.layers import LayerNormalization, Dense, Input, Concatenate, Reshape
from tensorflow.keras.initializers import RandomNormal
import numpy as np

class VisualTransformer():
    def __init__(self, input_resolution: int, patch_size: int, width: int, layers: int, heads: int, output_dim: int, name="VisualTransformer"):
        self.input_resolution: int = input_resolution
        self.patch_size: int = patch_size
        self.width: int = width
        self.num_layers: int = layers
        self.heads: int = heads
        self.output_dim: int = output_dim
        self.name = name

        self.conv1 = klayers.Conv2D(width, patch_size, strides=patch_size, use_bias=False, name=f"{name}/conv1")

        scale = width ** -0.5

        self.transformer = Transformer(width, layers, heads, name=f"{name}//transformer")()

        self.class_embedding = K.constant(scale * np.random.random((width,)), name=f"{name}/class_embedding")
        self.positional_embedding = K.constant(scale * tf.random.normal(((input_resolution // patch_size) ** 2 + 1, width)), name=f"{name}/positional_embedding")
        self.ln_pre = keras.layers.LayerNormalization(epsilon=1e-05, name=f"{name}/ln_pre")

        self.ln_post = keras.layers.LayerNormalization(epsilon=1e-05, name=f"{name}/ln_post")
        self.proj = K.constant(scale * np.random.random((width, output_dim)), name=f"{name}/proj")

    def get_config(self):
        return {
            "input_resolution": self.input_resolution,
            "patch_size": self.patch_size,
            "width": self.width,
            "layers": self.num_layers,
            "heads": self.heads,
            "output_dim": self.output_dim,
            "name": self.name
        }

    @classmethod
    def from_config(cls, config):
        return cls(**config)

    def __call__(self):
        inputs = Input([self.input_resolution, self.input_resolution, 3])
        var_x = self.conv1(inputs)  # shape = [*, grid, grid, width]

        x_shape = var_x.shape
        var_x = Reshape((196, self.width))(var_x)  # shape = [*, grid ** 2, width]

        x_shape = K.shape(var_x)
        class_embedding = K.expand_dims(K.expand_dims(K.cast(self.class_embedding, var_x.dtype),0),0)
        class_embedding_tiled = K.tile(class_embedding, [x_shape[0], 1, 1])
        var_x = Concatenate(axis=1)([class_embedding_tiled, var_x])
        var_x = var_x + K.cast(self.positional_embedding, var_x.dtype)
        var_x = self.ln_pre(var_x)
        var_x = self.transformer(var_x)
        var_x = self.ln_post(var_x[:, 0, :])

        if self.proj is not None:
            if var_x.dtype == tf.float16:
                var_x = K.cast(var_x, tf.float32) #TODO: remove this when tf.matmul supports float16 with float32
                var_x = var_x @ self.proj
                var_x = K.cast(var_x, tf.float16)
            else:
                var_x = var_x @ self.proj
        return Model(inputs=inputs, outputs=[var_x], name=self.name)
