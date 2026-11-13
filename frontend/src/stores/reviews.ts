import type {Ref} from 'vue';
import {entityStore} from "./entity";
import type {FormulaReview} from "../types/domain";
const base=entityStore("reviews");
export const reviews={...base,items:base.items as unknown as Ref<FormulaReview[]>};
