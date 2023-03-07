# -*- coding: utf-8 -*-
#
# Copyright 2022 Confluent Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import random
import murmurhash2


class Murmur2Partitioner:
    """
    Implements a partitioner which selects the target partition based on
    the hash of the key. Attempts to apply the same hashing
    function as mainline java client.
    """

    def partition(
        self,
        key: bytes,
        partitions: int,
    ) -> int:
        # https://github.com/apache/kafka/blob/0.8.2/clients/src/main/java/org/apache/kafka/clients/producer/internals/Partitioner.java#L69
        # Binary multiplication by 0x7FFFFFFF to make it a positive number
        if key is None:
            # Emulate murmur2_random partitioner
            return int(random.random() * 999999999999999) % partitions
        else:
            return (self._murmur2(key) & 0x7FFFFFFF) % partitions

    def _murmur2(
        self,
        data: bytes,
    ) -> int:
        return murmurhash2.murmurhash2(
            data,
            0x9747B28C,
        )


if __name__ == "__main__":
    p = Murmur2Partitioner()
    topic_partitions = 6
    print(f"Topic with {topic_partitions} partition(s):")

    partitions_count = dict()
    for i in range(1000):
        partition = p.partition(f"{i:03}".encode(), topic_partitions)
        print(f"Event content '{i:03}' -> partition #{partition}")
        partitions_count[partition] = partitions_count.get(partition, 0) + 1

    print("\nPartitions distribution:")
    for k, v in sorted(partitions_count.items()):
        print(f"#{k}: {v} event(s)")
