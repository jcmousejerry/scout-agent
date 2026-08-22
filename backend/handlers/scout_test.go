package handlers

import (
	"encoding/json"
	"testing"
)

func TestShouldPersistEliminated(t *testing.T) {
	tests := []struct {
		name        string
		messageType string
		value       json.RawMessage
		want        bool
	}{
		{"discussion cannot erase state", "discussion", nil, false},
		{"discussion ignores accidental list", "discussion", json.RawMessage(`["A"]`), false},
		{"elimination requires field", "elimination", nil, false},
		{"elimination rejects null", "elimination", json.RawMessage(`null`), false},
		{"elimination accepts cumulative list", "elimination", json.RawMessage(`["A","B"]`), true},
	}

	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			if got := shouldPersistEliminated(test.messageType, test.value); got != test.want {
				t.Fatalf("shouldPersistEliminated() = %v, want %v", got, test.want)
			}
		})
	}
}
