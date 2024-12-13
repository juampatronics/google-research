# coding=utf-8
# Copyright 2024 The Google Research Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""SwitchAction class."""

import dataclasses
from typing import Optional
import xmile_entity
import xmile_globals

__NAMESPACE__ = "http://docs.oasis-open.org/xmile/ns/XMILE/v1.0"


@dataclasses.dataclass(kw_only=True)
class XmileSwitchAction:
  """XmileSwitchAction class."""

  class Meta:
    name = "switch_action"
    namespace = xmile_globals.XMILE_NAMESPACE

  entity: Optional[xmile_entity.XmileEntity] = dataclasses.field(
      default=None,
      metadata={
          "type": "Element",
      },
  )
  group: Optional["XmileSwitchAction.Group"] = dataclasses.field(
      default=None,
      metadata={
          "type": "Element",
      },
  )

  @dataclasses.dataclass(kw_only=True)
  class Group:
    value: float = dataclasses.field(
        metadata={
            "type": "Element",
            "required": True,
        }
    )
    name: str = dataclasses.field(
        metadata={
            "type": "Attribute",
            "required": True,
        }
    )