<script>
import { Modal } from 'bootstrap';

export default {
    name: 'Mixture',
    props: {
        chemical_components: Array,
        show: Boolean
    },
    state: () => ({
        parts: [],
        modal: null
    }),
    methods: {
        addPart() {
            this.parts.push(null);
        },
        save(event) {
            console.log(event.target);
            this.close();
        },
        close() {
            this.$emit('close');
        }
    },
    mounted() {
        this.modal = new Modal(this.$refs.modal);
        console.log(this.modal, this.open);
    },
    watch: {
        show(newState, oldState) {
            if (newState == true) {
                this.modal.show();
            }
            else {
                this.modal.hide();
            }
        }
    }

}
</script>

<template>
    <!-- Modal -->
    <div ref="modal" class="modal fade" id="exampleModal" tabindex="-1" aria-labelledby="exampleModalLabel" :aria-hidden="show">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title" id="exampleModalLabel">Mix things</h5>
                    <button type="button" class="btn-close" @click="close" aria-label="Close"></button>
                </div>
                <div class="modal-body">
                    <select class="form-select" aria-label="Default select example">
                        <option v-for="chem in chemical_components" :key="chem">{{chem}}</option>
                    </select>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" @click="close">Close</button>
                    <button type="button" class="btn btn-primary" @click="save">Save changes</button>
                </div>
            </div>
        </div>
    </div>

</template>