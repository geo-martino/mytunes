from collections import Counter
from collections.abc import MutableSequence, Collection, Iterable
from copy import copy

from mytunes.core.sequence import UniqueSequence
from mytunes.processors.check._match._base import CheckerMatch
from mytunes.processors.check.result import CheckResult
from mytunes.core.properties.uri import HasURI, HasMutableURI


class PlaylistMatch[IT: HasMutableURI](CheckerMatch[IT]):
    async def match(self) -> CheckResult[IT]:
        """Match the given that have missing URIs with items in the current playlist."""
        self._logger.info(f"Checking for changes to items in {self.page.source} playlist: {self.name}", header=2)

        current = await self.page.get_current_playlist_items(self.uri)
        added, removed, unchanged, unavailable, missing = self._compare_items(others=current)

        if not added and not removed and not missing:
            message = "Playlist unchanged and no missing URIs, skipping match"
            self._log_debug("SKIP", message)
            return CheckResult(unchanged=unchanged, unavailable=unavailable, skipped=missing)

        missing += removed
        for item in missing:
            if isinstance(item, HasMutableURI):
                del item.uri

        if not missing:
            message = "No items changed in playlist and no items with missing matches, skipping match"
            self._log_debug("SKIP", message)
            return CheckResult(unchanged=unchanged, unavailable=unavailable)

        if not added:
            message = "No items added, skipping match"
            self._log_debug("SKIP", message)
            return CheckResult(unchanged=unchanged, unavailable=unavailable, skipped=missing)

        if not any(isinstance(item, HasMutableURI) for item in missing):
            message = "No items with mutable URIs to match with added items, skipping match"
            self._log_debug("SKIP", message)
            return CheckResult(unchanged=unchanged, unavailable=unavailable, skipped=missing)

        changed = self._match_items_with_others(items=missing, others=added)
        return CheckResult(changed=changed, unchanged=unchanged, unavailable=unavailable, skipped=missing)

    def _compare_items[RT: HasURI](
            self, others: Collection[RT]
    ) -> tuple[list[RT], list[IT], list[IT], list[IT], list[IT]]:
        valid_items = self.valid_items
        items_unique = UniqueSequence(valid_items)
        others_unique = UniqueSequence(others)

        added = list(others_unique.difference(items_unique))
        removed = list(items_unique.difference(others_unique))
        removed += self._compare_duplicate_items(valid_items, others, removed)
        unchanged = list(items_unique.intersection(others_unique))
        unavailable = self.unavailable_items
        missing = self.missing_items

        if self.page.use_existing_playlists and (initial := len(self.page.get_initial_playlist_items(self.uri))) > 0:
            initial_message = "items that were in the playlist before starting"
            self._log_debug("REMOTE", initial_message, count=initial)

        self._log_debug("REMOTE", "items at start", count=len(self.items))
        self._log_debug("REMOTE", "items that are confirmed as unavailable", count=len(unavailable))
        self._log_debug("REMOTE", "items added", count=len(added))
        self._log_debug("REMOTE", "items removed", count=len(removed))
        self._log_debug("REMOTE", "difference", count=len(added) - len(removed))
        self._log_debug("REMOTE", "items unchanged", count=len(unchanged))
        self._log_debug("REMOTE", "items still with missing URI", count=len(missing))
        self._log_debug("REMOTE", "total item changes", count=len(added) - len(removed))

        return added, removed, unchanged, unavailable, missing

    @staticmethod
    def _compare_duplicate_items(initial: Collection[IT], others: Iterable[HasURI], unique: list[IT]) -> list[IT]:
        # if item collection originally contained duplicate URIS and one or more of the duplicates were removed
        # find removed duplicate items by looking for changes in counts
        initial_counts = Counter(item.uri for item in initial)
        other_counts = Counter(item.uri for item in others)
        current_counts = Counter(item.uri for item in unique)

        duplicates = []
        for item in initial:
            initial_count = initial_counts.get(item.uri, 0)
            other_count = other_counts.get(item.uri, 0)
            current_count = current_counts.get(item.uri, 0)

            if initial_count == 1 or initial_count <= current_count + other_count:
                continue

            duplicates.append(item)
            current_counts = Counter(item.uri for item in unique + duplicates)  # refresh counts

        return duplicates

    def _match_items_with_others(self, items: MutableSequence[IT], others: MutableSequence[HasURI]) -> list[IT]:
        initial = len(items)
        changed = []

        for item in copy(items):  # copy to safely modify items while iterating
            if not others:
                break

            match = self._match_item_with_others(item, others, "REMOTE")
            if match is None:
                continue

            changed.append(item)
            items.remove(item)
            others.remove(match)

        final = len(items)
        self._log_debug("REMOTE", "items switched", count=initial - final)
        self._log_debug("REMOTE", "items still not found", count=final)

        return changed
