// Copyright 2025 The Google Research Authors.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

#ifndef SCANN_HASHES_INTERNAL_LUT16_HIGHWAY_H_
#define SCANN_HASHES_INTERNAL_LUT16_HIGHWAY_H_
#include <cstdint>

#include "scann/hashes/internal/lut16_args.h"
#include "scann/utils/intrinsics/attributes.h"

namespace research_scann {
namespace asymmetric_hashing_internal {

template <size_t kNumQueries, PrefetchStrategy kPrefetch>
class LUT16Highway {
 public:
  SCANN_HIGHWAY_OUTLINE static void GetInt16Distances(LUT16Args<int16_t> args);
  SCANN_HIGHWAY_OUTLINE static void GetInt32Distances(LUT16Args<int32_t> args);

  SCANN_HIGHWAY_OUTLINE static void GetTopInt16Distances(
      LUT16ArgsTopN<int16_t> args);
  SCANN_HIGHWAY_OUTLINE static void GetTopFloatDistances(
      LUT16ArgsTopN<float> args);

  SCANN_HIGHWAY_OUTLINE static void GetFloatDistances(
      LUT16Args<float> args, ConstSpan<float> inv_fp_multipliers);
};

SCANN_INSTANTIATE_CLASS_FOR_LUT16_BATCH_SIZES(extern, LUT16Highway);

}  // namespace asymmetric_hashing_internal
}  // namespace research_scann

#endif
